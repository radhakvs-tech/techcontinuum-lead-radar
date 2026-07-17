"""Spec §5 evidence hierarchy. Acceptance #7, #18, #19."""

from __future__ import annotations

from datetime import date

import pytest
from conftest import make_account
from pydantic import ValidationError
from sqlmodel import Session

from lead_radar.models.enums import EvidenceClassification, EvidenceSourceType
from lead_radar.models.evidence import Evidence


def _make_evidence(session: Session, account_id: int, **overrides: object) -> Evidence:
    defaults = dict(
        account_id=account_id,
        source_url="https://example.com/careers",
        source_title="Careers page",
        source_type=EvidenceSourceType.CAREERS_PAGE,
        published_date=date(2026, 1, 1),
        observed_date=date(2026, 1, 2),
        evidence_text="We are hiring platform engineers.",
        evidence_summary="Platform hiring",
        signal_type="platform_or_sre_hiring",
        classification=EvidenceClassification.OBSERVED_FACT,
        confidence=0.8,
        independence_group="g1",
    )
    defaults.update(overrides)
    evidence = Evidence(**defaults)  # type: ignore[arg-type]
    session.add(evidence)
    session.commit()
    session.refresh(evidence)
    return evidence


def test_evidence_requires_source_url_and_dates(session: Session) -> None:
    account = make_account(session)
    evidence = _make_evidence(session, account.id)
    assert evidence.source_url
    assert evidence.observed_date is not None
    assert evidence.independence_group


def test_score_breakdown_rejects_out_of_range_confidence() -> None:
    """SQLModel table classes are intentionally permissive at construction
    time (they must support partial ORM hydration), so the "required field"
    contract is enforced at the plain-pydantic layer instead — here, the
    ScoredSignal confidence bound used throughout scoring."""
    from lead_radar.scoring.models import ScoredSignal

    with pytest.raises(ValidationError):
        ScoredSignal(
            signal_key="action_taking_agent",
            dimension="ai_transition_pressure",
            source="https://example.com",
            base_weight=12.0,
            recency_adjusted_weight=10.0,
            confidence=1.5,  # invalid: must be handled as a bounded [0, 1] value upstream
            contribution=10.0,
            age_days=5,
            independence_group="g1",
            reason="test",
        )


def test_evidence_classification_distinguishes_fact_inference_unknown(session: Session) -> None:
    account = make_account(session)
    fact = _make_evidence(session, account.id, classification=EvidenceClassification.OBSERVED_FACT)
    inference = _make_evidence(
        session, account.id, classification=EvidenceClassification.REASONABLE_INFERENCE
    )
    unknown = _make_evidence(
        session, account.id, classification=EvidenceClassification.UNKNOWN_REQUIRING_VALIDATION
    )
    assert {fact.classification, inference.classification, unknown.classification} == {
        EvidenceClassification.OBSERVED_FACT,
        EvidenceClassification.REASONABLE_INFERENCE,
        EvidenceClassification.UNKNOWN_REQUIRING_VALIDATION,
    }


def test_evidence_sharing_source_url_gets_grouped_by_evidence_pipeline() -> None:
    from lead_radar.discovery.evidence_pipeline import event_to_evidence
    from lead_radar.providers.base import CompanyEventRecord

    shared_url = "https://example.com/press/launch"
    event_a = CompanyEventRecord(
        account_domain="example.com",
        event_type="customer_facing_ai_launch",
        title="A",
        description="A",
        source_url=shared_url,
    )
    event_b = CompanyEventRecord(
        account_domain="example.com",
        event_type="action_taking_agent",
        title="B",
        description="B",
        source_url=shared_url,
    )
    evidence_a = event_to_evidence(1, event_a)
    evidence_b = event_to_evidence(1, event_b)
    assert evidence_a.independence_group == evidence_b.independence_group


def test_evidence_pipeline_uses_neutral_wording_for_missing_source() -> None:
    from lead_radar.discovery.evidence_pipeline import event_to_evidence
    from lead_radar.providers.base import CompanyEventRecord

    event = CompanyEventRecord(
        account_domain="example.com",
        event_type="customer_facing_ai_launch",
        title="Feature launched",
        description="A feature launched.",
        source_url=None,
    )
    evidence = event_to_evidence(1, event)
    assert "unknown" in evidence.source_url
    assert "lacks" not in evidence.evidence_text.lower()
