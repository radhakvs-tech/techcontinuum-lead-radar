"""Persists a ScoreBreakdown onto the ScoreRun / ScoreContribution tables."""

from __future__ import annotations

from sqlmodel import Session

from lead_radar.models.scoring import ScoreContribution, ScoreRun
from lead_radar.scoring.models import ScoreBreakdown


def persist_score_run(session: Session, breakdown: ScoreBreakdown) -> ScoreRun:
    run = ScoreRun(
        account_id=breakdown.account_id,
        scoring_version=breakdown.scoring_version,
        icp_score=breakdown.icp_score,
        ai_transition_score=breakdown.ai_transition_score,
        cloud_modernisation_score=breakdown.cloud_modernisation_score,
        martech_pressure_score=breakdown.martech_pressure_score,
        advisor_fit_score=breakdown.advisor_fit_score,
        evidence_score=breakdown.evidence_score,
        total_score=breakdown.total_score,
        classification=breakdown.classification,
        meets_high_intent_evidence_bar=breakdown.meets_high_intent_evidence_bar,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    for contribution in breakdown.signal_contributions:
        session.add(
            ScoreContribution(
                score_run_id=run.id,
                signal_key=contribution.signal_key,
                source=contribution.source,
                dimension=contribution.dimension,
                signal_date=contribution.signal_date,
                original_weight=contribution.base_weight,
                recency_adjusted_weight=contribution.recency_adjusted_weight,
                confidence=contribution.confidence,
                contribution=contribution.contribution,
                reason=contribution.reason,
                cap_applied=contribution.cap_applied,
            )
        )
    session.commit()
    return run
