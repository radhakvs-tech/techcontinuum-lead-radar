"""Spec §8 recency decay, §5/§18.15 missing-date handling. Acceptance #6, #15."""

from __future__ import annotations

import math
from datetime import date, timedelta

from lead_radar.scoring.recency import (
    MISSING_DATE_CONFIDENCE_PENALTY,
    MISSING_DATE_HALF_LIFE_MULTIPLES,
    effective_weight,
    recency_multiplier,
    resolve_age_and_confidence,
)


def test_recency_multiplier_matches_half_life_formula() -> None:
    assert math.isclose(recency_multiplier(0, 90), 1.0)
    assert math.isclose(recency_multiplier(90, 90), 0.5)
    assert math.isclose(recency_multiplier(180, 90), 0.25)


def test_older_signal_has_lower_effective_weight() -> None:
    fresh = effective_weight(10.0, 0.8, age_days=5, half_life_days=90)
    stale = effective_weight(10.0, 0.8, age_days=400, half_life_days=90)
    assert stale < fresh
    assert stale > 0  # decays toward zero but never becomes negative from decay alone


def test_missing_signal_date_is_treated_conservatively() -> None:
    today = date(2026, 1, 1)
    age_with_date, confidence_with_date = resolve_age_and_confidence(
        today - timedelta(days=30), half_life_days=90, confidence=0.8, today=today
    )
    age_missing, confidence_missing = resolve_age_and_confidence(
        None, half_life_days=90, confidence=0.8, today=today
    )

    assert age_missing > age_with_date
    assert age_missing == int(90 * MISSING_DATE_HALF_LIFE_MULTIPLES)
    assert confidence_missing < confidence_with_date
    assert confidence_missing == 0.8 * MISSING_DATE_CONFIDENCE_PENALTY


def test_missing_date_yields_lower_effective_weight_than_recent_known_date() -> None:
    today = date(2026, 1, 1)
    age_known, conf_known = resolve_age_and_confidence(
        today - timedelta(days=5), half_life_days=90, confidence=0.8, today=today
    )
    age_missing, conf_missing = resolve_age_and_confidence(
        None, half_life_days=90, confidence=0.8, today=today
    )

    known_weight = effective_weight(10.0, conf_known, age_known, 90)
    missing_weight = effective_weight(10.0, conf_missing, age_missing, 90)
    assert missing_weight < known_weight
