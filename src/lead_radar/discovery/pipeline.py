"""End-to-end account-first pipeline: search -> hard gates -> low-cost
signal enrichment -> score. Spec §6 "Account-first workflow".

Public web research, LLM classification and contact discovery are later
phases and are not called from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlmodel import Session, select

from lead_radar.discovery.evidence_pipeline import ingest_events
from lead_radar.discovery.ingest import ingest_company_record
from lead_radar.models.account import Account
from lead_radar.models.enums import AccountStatus, Classification
from lead_radar.models.evidence import Evidence
from lead_radar.models.scoring import ScoreContribution, ScoreRun
from lead_radar.providers.base import CompanyDataProvider
from lead_radar.scoring.engine import is_martech_account, score_account
from lead_radar.scoring.offers import primary_pain_track, select_offer
from lead_radar.scoring.persistence import persist_score_run

# Classifications that require a human decision before the account can move
# forward (spec §10: no company moves directly from discovery to contact
# enrichment).
REVIEW_REQUIRED_CLASSIFICATIONS = {
    Classification.HIGH_INTENT,
    Classification.HIGH_PRIORITY_REVIEW,
    Classification.WATCHLIST,
    Classification.GOOD_FIT_LOW_SIGNAL,
}


@dataclass
class ScoredAccountResult:
    account: Account
    score_run: ScoreRun
    contributions: list[ScoreContribution]
    primary_pain_track: str
    recommended_offer: str


@dataclass
class PipelineRunResult:
    provider_name: str
    accounts_discovered: int = 0
    accounts_rejected: int = 0
    accounts_scored: list[ScoredAccountResult] = field(default_factory=list)
    rejected_accounts: list[Account] = field(default_factory=list)
    evidence_rows: list[tuple[Evidence, Account]] = field(default_factory=list)
    provider_errors: list[str] = field(default_factory=list)


def run_discovery_pipeline(
    session: Session,
    provider: CompanyDataProvider,
    countries: list[str] | None = None,
) -> PipelineRunResult:
    result = PipelineRunResult(provider_name=getattr(provider, "name", provider.__class__.__name__))

    try:
        records = (
            provider.search_companies(countries=countries)
            if countries
            else provider.search_companies()
        )
    except Exception as exc:  # noqa: BLE001 - a provider failure must not crash the run
        result.provider_errors.append(f"search_companies failed: {exc}")
        return result

    result.accounts_discovered = len(records)

    for record in records:
        account = ingest_company_record(session, record)
        assert account.id is not None  # always set: ingest_company_record persists the account

        if account.status == AccountStatus.REJECTED:
            result.accounts_rejected += 1
            result.rejected_accounts.append(account)
            continue

        try:
            events = provider.get_company_events(record.domain)
        except Exception as exc:  # noqa: BLE001
            result.provider_errors.append(f"get_company_events({record.domain}) failed: {exc}")
            events = []

        signals = ingest_events(session, account.id, events) if events else []

        evidence_ids = [s.evidence_id for s in signals if s.evidence_id is not None]
        evidence_by_id: dict[int, Evidence] = {}
        for evidence_id in evidence_ids:
            evidence = session.get(Evidence, evidence_id)
            if evidence is not None:
                evidence_by_id[evidence_id] = evidence
                result.evidence_rows.append((evidence, account))

        account.status = AccountStatus.SCORED
        breakdown = score_account(account, signals, evidence_by_id)
        score_run = persist_score_run(session, breakdown)

        pain_track = primary_pain_track(breakdown)
        offer_code, _rationale = select_offer(breakdown, is_martech_account(account))

        if breakdown.classification in REVIEW_REQUIRED_CLASSIFICATIONS:
            account.status = AccountStatus.PENDING_HUMAN_REVIEW
        session.add(account)
        session.commit()
        session.refresh(account)

        contributions = _fetch_contributions(session, score_run)

        result.accounts_scored.append(
            ScoredAccountResult(
                account=account,
                score_run=score_run,
                contributions=contributions,
                primary_pain_track=pain_track,
                recommended_offer=offer_code.value,
            )
        )

    return result


def _fetch_contributions(session: Session, score_run: ScoreRun) -> list[ScoreContribution]:
    return list(
        session.exec(
            select(ScoreContribution).where(ScoreContribution.score_run_id == score_run.id)
        )
    )
