"""Row shapes for the report outputs. Spec §15."""

from __future__ import annotations

from pydantic import BaseModel

from lead_radar.models.account import Account
from lead_radar.models.scoring import ScoreContribution, ScoreRun


class QualifiedAccountRow(BaseModel):
    company: str
    domain: str
    country: str
    employee_count: str
    revenue_range: str
    arr_confidence: str
    industry: str
    primary_pain_track: str
    recommended_offer: str
    icp_score: float
    ai_transition_score: float
    cloud_modernisation_score: float
    sector_pressure_score: float
    advisor_fit_score: float
    evidence_score: float
    total_score: float
    classification: str
    top_signal_1: str
    top_signal_2: str
    top_signal_3: str
    signal_dates: str
    evidence_urls: str
    unknowns: str
    review_status: str
    scoring_version: str


def _revenue_range(account: Account) -> str:
    if account.reported_revenue_usd is not None:
        return f"reported:{account.reported_revenue_usd:,.0f}"
    if account.revenue_min_usd is not None and account.revenue_max_usd is not None:
        return f"estimated:{account.revenue_min_usd:,.0f}-{account.revenue_max_usd:,.0f}"
    return "unknown"


def build_qualified_account_row(
    account: Account,
    score_run: ScoreRun,
    contributions: list[ScoreContribution],
    primary_pain_track: str,
    recommended_offer: str,
) -> QualifiedAccountRow:
    material = sorted(
        (c for c in contributions if c.contribution != 0),
        key=lambda c: -abs(c.contribution),
    )
    top_signals = [c.signal_key for c in material[:3]]
    top_signals += [""] * (3 - len(top_signals))

    dates = sorted({c.signal_date.isoformat() for c in material if c.signal_date is not None})
    urls = sorted({c.source for c in material if c.source and c.source != "unknown"})

    return QualifiedAccountRow(
        company=account.company_name,
        domain=account.domain,
        country=account.headquarters_country or "unknown",
        employee_count=str(account.employee_count)
        if account.employee_count is not None
        else "unknown",
        revenue_range=_revenue_range(account),
        arr_confidence=account.arr_confidence.value,
        industry=account.industry or "unknown",
        primary_pain_track=primary_pain_track,
        recommended_offer=recommended_offer,
        icp_score=score_run.icp_score,
        ai_transition_score=score_run.ai_transition_score,
        cloud_modernisation_score=score_run.cloud_modernisation_score,
        sector_pressure_score=score_run.martech_pressure_score,
        advisor_fit_score=score_run.advisor_fit_score,
        evidence_score=score_run.evidence_score,
        total_score=score_run.total_score,
        classification=score_run.classification.value,
        top_signal_1=top_signals[0],
        top_signal_2=top_signals[1],
        top_signal_3=top_signals[2],
        signal_dates="; ".join(dates) if dates else "unknown",
        evidence_urls="; ".join(urls) if urls else "unknown",
        unknowns="; ".join(account.data_quality_flags) if account.data_quality_flags else "",
        review_status=account.status.value,
        scoring_version=score_run.scoring_version,
    )
