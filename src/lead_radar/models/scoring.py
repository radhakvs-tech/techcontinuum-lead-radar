"""ScoreRun and ScoreContribution entities. Spec §8 (deterministic scoring)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlmodel import Field, SQLModel

from lead_radar.models.enums import Classification


class ScoreRun(SQLModel, table=True):
    """One deterministic scoring pass over an account, fully reproducible
    from its ScoreContribution rows plus scoring_version."""

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True)
    scoring_version: str

    icp_score: float = 0.0
    ai_transition_score: float = 0.0
    cloud_modernisation_score: float = 0.0
    martech_pressure_score: float = 0.0
    advisor_fit_score: float = 0.0
    evidence_score: float = 0.0
    total_score: float = 0.0

    classification: Classification = Classification.INSUFFICIENT_INFORMATION
    meets_high_intent_evidence_bar: bool = False

    run_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ScoreContribution(SQLModel, table=True):
    """One line item in a ScoreRun's explainable breakdown (spec §8 Explainability)."""

    id: int | None = Field(default=None, primary_key=True)
    score_run_id: int = Field(foreign_key="scorerun.id", index=True)

    signal_key: str
    source: str  # evidence source_url or description
    dimension: str
    signal_date: date | None = None

    original_weight: float
    recency_adjusted_weight: float
    confidence: float
    contribution: float  # signed: positive or negative

    reason: str
    cap_applied: str | None = None
