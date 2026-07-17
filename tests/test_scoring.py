"""Spec §8 deterministic scoring. Acceptance criteria #4, #5, #7, #8, #13."""

from __future__ import annotations

from datetime import date, timedelta

from conftest import make_account
from sqlmodel import Session

from lead_radar.models.enums import Classification, EvidenceClassification, EvidenceSourceType
from lead_radar.models.evidence import Evidence, Signal
from lead_radar.scoring.engine import score_account

TODAY = date(2026, 7, 16)


def _signal(
    account_id: int,
    signal_key: str,
    days_ago: int | None,
    confidence: float = 0.8,
    independence_group: str = "group-a",
    evidence_id: int | None = None,
) -> Signal:
    return Signal(
        account_id=account_id,
        evidence_id=evidence_id,
        signal_key=signal_key,
        signal_date=None if days_ago is None else TODAY - timedelta(days=days_ago),
        confidence=confidence,
        independence_group=independence_group,
    )


def test_generic_ai_marketing_alone_cannot_produce_high_intent(session: Session) -> None:
    account = make_account(session, company_type="b2b_saas")
    signals = [_signal(account.id, "generic_ai_marketing_only", days_ago=5)]
    breakdown = score_account(account, signals, {}, today=TODAY)

    assert breakdown.classification != Classification.HIGH_INTENT
    assert breakdown.meets_high_intent_evidence_bar is False


def test_simultaneous_ai_and_platform_hiring_increases_score_materially(session: Session) -> None:
    account = make_account(session, company_type="b2b_saas")

    baseline_signals = [
        _signal(account.id, "multiple_ai_roles", days_ago=10, independence_group="g1")
    ]
    baseline = score_account(account, baseline_signals, {}, today=TODAY)

    enhanced_signals = baseline_signals + [
        _signal(account.id, "platform_or_sre_hiring", days_ago=10, independence_group="g2"),
        _signal(
            account.id, "simultaneous_ai_and_platform_hiring", days_ago=10, independence_group="g3"
        ),
    ]
    enhanced = score_account(account, enhanced_signals, {}, today=TODAY)

    assert enhanced.total_score > baseline.total_score + 5  # materially higher, not noise


def test_two_signals_from_same_source_are_not_independent(session: Session) -> None:
    # employee_count kept outside the 50-200 advisor-fit band so the
    # structural employee_band_50_200 signal doesn't add a second
    # independent group and mask what this test is checking.
    account = make_account(session, company_type="b2b_saas", employee_count=300)
    same_source_signals = [
        _signal(
            account.id,
            "customer_facing_ai_launch",
            days_ago=10,
            independence_group="same-press-release",
        ),
        _signal(
            account.id, "action_taking_agent", days_ago=10, independence_group="same-press-release"
        ),
    ]
    breakdown = score_account(account, same_source_signals, {}, today=TODAY)
    positive = [c for c in breakdown.signal_contributions if c.contribution > 0]
    independent_groups = {c.independence_group for c in positive}

    assert len(independent_groups) == 1
    # Only one independent group present, so the independent-signal bar (>=2) fails
    # even though two signals fired.
    assert breakdown.meets_high_intent_evidence_bar is False


def test_high_intent_requires_recent_direct_commitment_signal(session: Session) -> None:
    account = make_account(session, company_type="b2b_saas")

    # Two independent signals, both direct commitments, but both stale (400 days).
    stale_signals = [
        _signal(account.id, "customer_facing_ai_launch", days_ago=400, independence_group="g1"),
        _signal(account.id, "action_taking_agent", days_ago=400, independence_group="g2"),
    ]
    stale_breakdown = score_account(account, stale_signals, {}, today=TODAY)
    assert stale_breakdown.meets_high_intent_evidence_bar is False

    fresh_signals = [
        _signal(account.id, "customer_facing_ai_launch", days_ago=10, independence_group="g1"),
        _signal(account.id, "action_taking_agent", days_ago=15, independence_group="g2"),
    ]
    fresh_breakdown = score_account(account, fresh_signals, {}, today=TODAY)
    assert fresh_breakdown.meets_high_intent_evidence_bar is True


def test_score_contributions_reference_evidence_source(session: Session) -> None:
    # employee_count kept outside the 50-200 advisor-fit band so the
    # structural employee_band_50_200 signal (source="account.employee_count")
    # doesn't join the evidence-sourced signals this test is checking.
    account = make_account(session, company_type="b2b_saas", employee_count=300)
    evidence = Evidence(
        account_id=account.id,
        source_url="https://example.com/press/launch",
        source_title="Launch announcement",
        source_type=EvidenceSourceType.PRESS_RELEASE,
        published_date=TODAY - timedelta(days=10),
        observed_date=TODAY - timedelta(days=10),
        evidence_text="We launched an autonomous agent.",
        evidence_summary="Autonomous agent launch",
        signal_type="action_taking_agent",
        classification=EvidenceClassification.OBSERVED_FACT,
        confidence=0.8,
        independence_group="g1",
    )
    session.add(evidence)
    session.commit()
    session.refresh(evidence)

    signal = _signal(account.id, "action_taking_agent", days_ago=10, evidence_id=evidence.id)
    breakdown = score_account(account, [signal], {evidence.id: evidence}, today=TODAY)

    material = [c for c in breakdown.signal_contributions if c.contribution > 0]
    assert material
    assert all(c.source == evidence.source_url for c in material)


def test_non_martech_reallocation_preserves_total_available_points() -> None:
    from lead_radar.scoring.engine import dimension_max_points
    from lead_radar.settings import get_scoring_config

    scoring_data = get_scoring_config().data
    martech_points = dimension_max_points(is_martech=True, scoring_config_data=scoring_data)
    non_martech_points = dimension_max_points(is_martech=False, scoring_config_data=scoring_data)

    assert sum(martech_points.values()) == sum(non_martech_points.values())
    assert non_martech_points["martech_agentisation_pressure"] == 0.0


def test_scoring_is_deterministic(session: Session) -> None:
    account = make_account(session, company_type="b2b_saas")
    signals = [_signal(account.id, "customer_facing_ai_launch", days_ago=10)]
    first = score_account(account, signals, {}, today=TODAY)
    second = score_account(account, signals, {}, today=TODAY)
    assert first.total_score == second.total_score
    assert first.classification == second.classification
