"""Spec §12 dedup by canonical domain. Acceptance #14, #17, §22 idempotent imports."""

from __future__ import annotations

from sqlmodel import Session, select

from lead_radar.discovery.ingest import (
    HARD_GATE_MISMATCH_FLAG_PREFIX,
    canonicalize_domain,
    ingest_company_record,
)
from lead_radar.models.account import Account
from lead_radar.models.enums import AccountStatus
from lead_radar.providers.base import ProviderCompanyRecord
from lead_radar.review.workflow import apply_review_decision


def test_canonicalize_domain_normalises_variants() -> None:
    assert canonicalize_domain("https://Example.com/") == "example.com"
    assert canonicalize_domain("http://www.example.com") == "example.com"
    assert canonicalize_domain("EXAMPLE.com/about") == "example.com"


def test_duplicate_domain_merges_into_one_account(session: Session) -> None:
    record = ProviderCompanyRecord(
        company_name="Example Co",
        domain="example-co.example",
        headquarters_country="US",
        employee_count=100,
        reported_revenue_usd=50_000_000,
        company_type="b2b_saas",
    )
    ingest_company_record(session, record)
    ingest_company_record(session, record)

    accounts = list(session.exec(select(Account).where(Account.domain == "example-co.example")))
    assert len(accounts) == 1


def test_reingesting_updates_existing_account_fields(session: Session) -> None:
    record_v1 = ProviderCompanyRecord(
        company_name="Example Co",
        domain="example-co.example",
        headquarters_country="US",
        employee_count=100,
        reported_revenue_usd=50_000_000,
        company_type="b2b_saas",
    )
    first = ingest_company_record(session, record_v1)
    first_id = first.id

    record_v2 = record_v1.model_copy(update={"employee_count": 150})
    second = ingest_company_record(session, record_v2)

    assert second.id == first_id
    assert second.employee_count == 150


def test_alias_domain_variants_canonicalize_to_the_same_account(session: Session) -> None:
    base = ProviderCompanyRecord(
        company_name="Example Co",
        domain="example-co.example",
        headquarters_country="US",
        employee_count=100,
        reported_revenue_usd=50_000_000,
        company_type="b2b_saas",
    )
    aliased = base.model_copy(update={"domain": "https://www.example-co.example/"})

    ingest_company_record(session, base)
    ingest_company_record(session, aliased)

    accounts = list(session.exec(select(Account).where(Account.domain == "example-co.example")))
    assert len(accounts) == 1


def _base_record() -> ProviderCompanyRecord:
    return ProviderCompanyRecord(
        company_name="Example Co",
        domain="example-co.example",
        headquarters_country="US",
        employee_count=100,
        reported_revenue_usd=50_000_000,
        company_type="b2b_saas",
    )


def test_reingesting_without_human_review_keeps_auto_status_behaviour(session: Session) -> None:
    """Baseline: this fix only changes behaviour once a human has actually
    decided on the account — no HumanReview row means status keeps being
    auto-set from hard gates, same as before."""
    ingest_company_record(session, _base_record())
    updated = ingest_company_record(session, _base_record())
    assert updated.status == AccountStatus.PRELIMINARY_QUALIFIED


def test_reingesting_approved_account_preserves_status_and_refreshes_fields(
    session: Session,
) -> None:
    account = ingest_company_record(session, _base_record())
    apply_review_decision(
        session, account, "reviewer", AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY, "good fit"
    )

    record_v2 = _base_record().model_copy(update={"employee_count": 150, "industry": "SaaS"})
    updated = ingest_company_record(session, record_v2)

    assert updated.status == AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY
    assert updated.employee_count == 150
    assert updated.industry == "SaaS"


def test_reingesting_human_rejected_account_preserves_status_and_refreshes_fields(
    session: Session,
) -> None:
    """AccountStatus.REJECTED is written by both hard-gate auto-rejection
    and a human's `review reject` — a HumanReview row is what distinguishes
    them, and only the human-driven case must survive re-ingestion
    unchanged."""
    account = ingest_company_record(session, _base_record())
    apply_review_decision(session, account, "reviewer", AccountStatus.REJECTED, "wrong ICP")

    record_v2 = _base_record().model_copy(update={"employee_count": 150})
    updated = ingest_company_record(session, record_v2)

    assert updated.status == AccountStatus.REJECTED
    assert updated.employee_count == 150


def test_reingesting_approved_account_with_gate_failing_data_flags_not_overrides(
    session: Session,
) -> None:
    """If fresh data would now fail hard gates for a human-approved
    account, status must still be preserved — the mismatch is surfaced as
    a flag instead of silently re-rejecting an approved account."""
    account = ingest_company_record(session, _base_record())
    apply_review_decision(
        session, account, "reviewer", AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY, "good fit"
    )

    record_v2 = _base_record().model_copy(update={"headquarters_country": "FR"})
    updated = ingest_company_record(session, record_v2)

    assert updated.status == AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY
    mismatch_flags = [
        f for f in updated.data_quality_flags if f.startswith(HARD_GATE_MISMATCH_FLAG_PREFIX)
    ]
    assert len(mismatch_flags) == 1
    assert "headquarters_country" in mismatch_flags[0]
    assert "APPROVED_FOR_CONTACT_DISCOVERY" in mismatch_flags[0]


def test_reingesting_approved_account_still_passing_gates_adds_no_mismatch_flag(
    session: Session,
) -> None:
    account = ingest_company_record(session, _base_record())
    apply_review_decision(
        session, account, "reviewer", AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY, "good fit"
    )

    record_v2 = _base_record().model_copy(update={"employee_count": 120})
    updated = ingest_company_record(session, record_v2)

    assert not any(
        f.startswith(HARD_GATE_MISMATCH_FLAG_PREFIX) for f in updated.data_quality_flags
    )
