"""MockProvider — deterministic, offline implementation of CompanyDataProvider
for tests and the `make demo` walkthrough. Spec §6.
"""

from __future__ import annotations

from typing import Any

from lead_radar.providers.base import (
    CompanyEventRecord,
    ContactRecord,
    CostEstimate,
    ProviderCompanyRecord,
)
from lead_radar.providers.demo_fixtures import DEMO_COMPANIES


class MockProvider:
    """In-memory provider backed by the synthetic demo fixtures. Free (0 credits)."""

    name = "mock"

    def __init__(self) -> None:
        self._companies: dict[str, ProviderCompanyRecord] = {
            c.domain: c for c, _events in DEMO_COMPANIES
        }
        self._events: dict[str, list[CompanyEventRecord]] = {
            c.domain: events for c, events in DEMO_COMPANIES
        }

    def estimate_query_cost(self, operation: str, **params: Any) -> CostEstimate:
        return CostEstimate(
            operation=operation, estimated_credits=0.0, notes="mock provider is free"
        )

    def company_statistics(self, **filters: Any) -> dict[str, Any]:
        countries = filters.get("countries")
        matches = list(self._companies.values())
        if countries:
            matches = [c for c in matches if c.headquarters_country in countries]
        return {
            "total_companies": len(matches),
            "countries": sorted(
                {c.headquarters_country for c in matches if c.headquarters_country}
            ),
        }

    def search_companies(self, **filters: Any) -> list[ProviderCompanyRecord]:
        countries = filters.get("countries")
        results = list(self._companies.values())
        if countries:
            results = [c for c in results if c.headquarters_country in countries]
        return results

    def enrich_company(self, domain: str) -> ProviderCompanyRecord | None:
        return self._companies.get(domain)

    def get_company_events(self, domain: str) -> list[CompanyEventRecord]:
        return list(self._events.get(domain, []))

    def find_contacts(self, domain: str) -> list[ContactRecord]:
        return []

    def enrich_contact_email(self, contact: ContactRecord) -> ContactRecord:
        return contact
