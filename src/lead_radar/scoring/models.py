"""Pydantic value objects for a scoring pass. Spec §8 Explainability.

These are the in-memory shape scoring/engine.py produces; scoring/persistence.py
maps them onto the ScoreRun / ScoreContribution DB tables.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from lead_radar.models.enums import Classification


class ScoredSignal(BaseModel):
    signal_key: str
    dimension: str
    source: str
    signal_date: date | None = None

    base_weight: float
    recency_adjusted_weight: float
    confidence: float = Field(ge=0.0, le=1.0)
    contribution: float

    age_days: int | None
    independence_group: str

    reason: str
    cap_applied: str | None = None


class ScoreBreakdown(BaseModel):
    account_id: int
    scoring_version: str

    icp_score: float
    ai_transition_score: float
    cloud_modernisation_score: float
    martech_pressure_score: float
    advisor_fit_score: float
    evidence_score: float
    total_score: float

    classification: Classification
    meets_high_intent_evidence_bar: bool

    signal_contributions: list[ScoredSignal] = Field(default_factory=list)

    @property
    def dimension_scores(self) -> dict[str, float]:
        return {
            "icp_and_commercial_fit": self.icp_score,
            "ai_transition_pressure": self.ai_transition_score,
            "cloud_modernisation_pain": self.cloud_modernisation_score,
            "martech_agentisation_pressure": self.martech_pressure_score,
            "external_advisor_likelihood": self.advisor_fit_score,
            "evidence_quality_and_recency": self.evidence_score,
        }
