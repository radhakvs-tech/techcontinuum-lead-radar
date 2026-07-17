"""Recommended-offer matching. Spec §9.

This is deterministic Python, same as the rest of scoring/ — it just picks
among the four fixed TechContinuum offers based on which pain dimension the
account's scored evidence weighs toward most heavily. It is a first-pass
heuristic; refining offer selection with richer evidence is future work
(Phase 3+, once web research and LLM-assisted pain classification exist).
"""

from __future__ import annotations

from lead_radar.models.enums import OfferCode
from lead_radar.scoring.engine import is_martech_account
from lead_radar.scoring.models import ScoreBreakdown

MODERNISATION_SIGNAL_KEYS = {"explicit_modernisation_program"}
ECONOMICS_SIGNAL_KEYS = {"explicit_cloud_cost_signal", "finops_hiring"}

PAIN_TRACK_LABELS = {
    "ai_transition_pressure": "A_ai_production_readiness",
    "cloud_modernisation_pain": "B_C_cloud_and_modernisation",
    "martech_agentisation_pressure": "D_martech_agentisation",
}


def primary_pain_track(breakdown: ScoreBreakdown) -> str:
    scores = breakdown.dimension_scores
    candidates = {key: scores.get(key, 0.0) for key in PAIN_TRACK_LABELS}
    best = max(candidates, key=lambda k: candidates[k])
    return PAIN_TRACK_LABELS[best]


def select_offer(breakdown: ScoreBreakdown, is_martech: bool) -> tuple[OfferCode, str]:
    scores = breakdown.dimension_scores
    ai = scores.get("ai_transition_pressure", 0.0)
    cloud = scores.get("cloud_modernisation_pain", 0.0)
    martech = scores.get("martech_agentisation_pressure", 0.0)

    if is_martech and martech >= ai and martech >= cloud:
        return (
            OfferCode.OFFER_A_AGENTIC_MARTECH,
            "Established martech/customer-engagement platform where agentisation "
            "pressure is the strongest scored pain dimension.",
        )
    if ai >= cloud and ai >= martech:
        return (
            OfferCode.OFFER_B_AI_PRODUCTION_READINESS,
            "AI-transition pressure is the strongest scored pain dimension: evidence "
            "points to customer-facing AI moving from prototype toward production.",
        )

    modernisation_weight = sum(
        c.contribution
        for c in breakdown.signal_contributions
        if c.signal_key in MODERNISATION_SIGNAL_KEYS and c.contribution > 0
    )
    economics_weight = sum(
        c.contribution
        for c in breakdown.signal_contributions
        if c.signal_key in ECONOMICS_SIGNAL_KEYS and c.contribution > 0
    )
    if modernisation_weight >= economics_weight and modernisation_weight > 0:
        return (
            OfferCode.OFFER_D_AI_NATIVE_MODERNISATION,
            "Cloud/platform/modernisation pain is the strongest scored dimension, and the "
            "underlying evidence points specifically at architecture modernisation.",
        )
    return (
        OfferCode.OFFER_C_CLOUD_AI_UNIT_ECONOMICS,
        "Cloud/platform/modernisation pain is the strongest scored dimension, with "
        "evidence pointing at cost/economics pressure rather than a modernisation programme.",
    )


__all__ = ["is_martech_account", "primary_pain_track", "select_offer"]
