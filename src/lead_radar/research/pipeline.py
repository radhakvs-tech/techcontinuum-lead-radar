"""Research orchestrator: runs the spec §7 source sequence for one account
through a WebResearchProvider, persists structural Evidence, and records a
ResearchRun. Spec §7, §20 (Phase 3a).

Deliberately excludes everything Phase 3b owns: no LLM classification, no
Signal rows, no dossier generation, no offer matching. This only collects
and structurally tags Evidence — spec §5's evidence-quality tiers, applied
by keyword/structure rules (research/evidence_extraction.py), not by an
LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlmodel import Session, select

from lead_radar.models.account import Account
from lead_radar.models.enums import AccountStatus
from lead_radar.models.evidence import Evidence
from lead_radar.models.research import ResearchRun
from lead_radar.models.review import HumanReview
from lead_radar.models.scoring import ScoreRun
from lead_radar.research.source_sequence import ordered_roles
from lead_radar.settings import YamlConfig, get_providers_config

if TYPE_CHECKING:
    # Deferred to break the providers <-> research import cycle: providers/
    # web_research_base.py imports research/evidence_extraction.py, so this
    # module (imported by research/__init__.py) cannot import providers.*
    # at runtime. `from __future__ import annotations` already makes the
    # `WebResearchProvider` type hint below a lazy string, so this is only
    # needed for static type-checking.
    from lead_radar.providers.web_research_base import WebResearchProvider


@dataclass
class ResearchPipelineResult:
    account_id: int
    status: str = "not_started"  # not_started | skipped | completed
    skipped_reason: str | None = None
    pages_fetched: int = 0
    pages_skipped: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    research_run: ResearchRun | None = None


def _latest_score_run(session: Session, account_id: int) -> ScoreRun | None:
    return session.exec(
        select(ScoreRun)
        .where(ScoreRun.account_id == account_id)
        .order_by(ScoreRun.run_at.desc())  # type: ignore[attr-defined]
    ).first()


def _has_human_review(session: Session, account_id: int) -> bool:
    return (
        session.exec(select(HumanReview).where(HumanReview.account_id == account_id)).first()
        is not None
    )


def passes_preliminary_threshold(
    session: Session, account: Account, threshold: float
) -> tuple[bool, str]:
    """Spec §7: "search only accounts that have passed the preliminary
    score threshold." Reads the account's most recent ScoreRun rather than
    re-scoring here — research must never be the thing that decides
    whether an account is promising, only something gated by an already
    -computed, deterministic score."""
    if account.status == AccountStatus.REJECTED:
        return False, "account was rejected by ICP hard gates"
    latest_run = _latest_score_run(session, account.id) if account.id is not None else None
    if latest_run is None:
        return False, "account has no ScoreRun yet — run `lead-radar score` first"
    if latest_run.total_score < threshold:
        return (
            False,
            f"latest score {latest_run.total_score:.2f} is below "
            f"preliminary_score_threshold ({threshold:.2f})",
        )
    return True, "passed preliminary score threshold"


def run_research(
    session: Session,
    account: Account,
    provider: WebResearchProvider,
    providers_config: YamlConfig | None = None,
) -> ResearchPipelineResult:
    if account.id is None:
        raise ValueError("account must be persisted (have an id) before research")

    config = providers_config or get_providers_config()
    web_cfg = config["web_research"]
    threshold = float(web_cfg.get("preliminary_score_threshold", 45))

    result = ResearchPipelineResult(account_id=account.id)

    passed, reason = passes_preliminary_threshold(session, account, threshold)
    if not passed:
        result.status = "skipped"
        result.skipped_reason = reason
        return result

    search_results = provider.search(account.domain, roles=ordered_roles())

    for search_result in search_results:
        try:
            page = provider.fetch_page(search_result.url)
        except Exception as exc:  # noqa: BLE001 - one bad page must not abort the run
            result.pages_skipped.append(f"{search_result.url}: {exc}")
            continue

        result.pages_fetched += 1
        page_evidence = provider.extract_public_evidence(
            account.id, page, search_result.source_type
        )
        for evidence in page_evidence:
            session.add(evidence)
        result.evidence.extend(page_evidence)

    session.commit()
    for evidence in result.evidence:
        session.refresh(evidence)

    research_run = ResearchRun(
        account_id=account.id,
        provider=provider.name,
        pages_fetched=result.pages_fetched,
        status="completed",
        notes="; ".join(result.pages_skipped) if result.pages_skipped else None,
    )
    session.add(research_run)

    # Same "has a human decided" rule as discovery/ingest.py:
    # ingest_company_record — a HumanReview row, not the status enum value,
    # is the source of truth, so a later research re-run never clobbers a
    # human decision back to RESEARCHED.
    if not _has_human_review(session, account.id):
        account.status = AccountStatus.RESEARCHED
        session.add(account)

    session.commit()
    session.refresh(research_run)
    session.refresh(account)

    result.status = "completed"
    result.research_run = research_run
    return result
