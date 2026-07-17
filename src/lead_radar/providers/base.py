"""Provider abstraction so the application is never tightly coupled to Vibe
Prospecting or any single data source. Spec §6.

`CompanyDataProvider` is implemented by MockProvider and CsvProvider in
Phase 1. A VibeProvider backed by the `vpai` CLI arrives in Phase 2, once
its live tool schemas have been inspected — parameters here are therefore
kept intentionally generic (`**filters`) rather than shaped around Vibe's
actual API, which is not yet known.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from pydantic import BaseModel, Field


class CostEstimate(BaseModel):
    operation: str
    estimated_credits: float
    notes: str = ""


class ProviderCompanyRecord(BaseModel):
    """A company as returned by a data provider, before it becomes an Account."""

    company_name: str
    domain: str
    headquarters_country: str | None = None
    employee_count: int | None = None
    reported_revenue_usd: float | None = None
    industry: str | None = None
    business_model: str | None = None
    company_type: str | None = None
    technologies: list[str] = Field(default_factory=list)
    # Provider-specific fields that don't map to a known Account column yet.
    raw: dict[str, Any] = Field(default_factory=dict)


class CompanyEventRecord(BaseModel):
    """A dated business/product event for a company (funding, launch, hire, ...)."""

    account_domain: str
    event_type: str
    title: str
    description: str
    event_date: date | None = None
    source_url: str | None = None
    confidence: float = 0.8


class ContactRecord(BaseModel):
    """A candidate contact. Retrieval is gated by review/guardrails.py — this
    is a data shape only, not a permission grant."""

    account_domain: str
    name: str
    exact_title: str
    public_profile_url: str | None = None
    role_change_date: date | None = None
    email: str | None = None


class CompanyDataProvider(Protocol):
    """Protocol every company data source (mock, CSV, Vibe) must satisfy."""

    name: str

    def estimate_query_cost(self, operation: str, **params: Any) -> CostEstimate: ...

    def company_statistics(self, **filters: Any) -> dict[str, Any]: ...

    def search_companies(self, **filters: Any) -> list[ProviderCompanyRecord]: ...

    def enrich_company(self, domain: str) -> ProviderCompanyRecord | None: ...

    def get_company_events(self, domain: str) -> list[CompanyEventRecord]: ...

    def find_contacts(self, domain: str) -> list[ContactRecord]: ...

    def enrich_contact_email(self, contact: ContactRecord) -> ContactRecord: ...
