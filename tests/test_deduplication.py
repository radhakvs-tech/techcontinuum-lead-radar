"""Spec §12 dedup by canonical domain. Acceptance #14, #17, §22 idempotent imports."""

from __future__ import annotations

from sqlmodel import Session, select

from lead_radar.discovery.ingest import canonicalize_domain, ingest_company_record
from lead_radar.models.account import Account
from lead_radar.providers.base import ProviderCompanyRecord


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
