"""Recency decay math. Spec §8.

effective_weight = base_weight * confidence * (0.5 ** (age_days / half_life_days))

Signals with an unknown date are handled conservatively (spec §5, §18.15):
treated as several half-lives old *and* confidence-penalised, rather than
assumed to have happened today.
"""

from __future__ import annotations

from datetime import date

MISSING_DATE_HALF_LIFE_MULTIPLES = 3
MISSING_DATE_CONFIDENCE_PENALTY = 0.5


def recency_multiplier(age_days: int, half_life_days: float) -> float:
    return float(0.5 ** (age_days / half_life_days))


def effective_weight(
    base_weight: float, confidence: float, age_days: int, half_life_days: float
) -> float:
    return base_weight * confidence * recency_multiplier(age_days, half_life_days)


def resolve_age_and_confidence(
    signal_date: date | None,
    half_life_days: float,
    confidence: float,
    today: date,
) -> tuple[int, float]:
    if signal_date is None:
        return int(
            half_life_days * MISSING_DATE_HALF_LIFE_MULTIPLES
        ), confidence * MISSING_DATE_CONFIDENCE_PENALTY
    age_days = (today - signal_date).days
    return max(age_days, 0), confidence
