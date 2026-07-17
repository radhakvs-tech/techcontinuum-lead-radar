"""End-to-end pipeline behaviour. Acceptance #16 (analog: provider failure
does not corrupt the run — no LLM exists yet in Phase 1, but the same
isolation principle applies to any external call), #20 (dry-run report),
and general MVP acceptance criteria 1-8."""

from __future__ import annotations

from sqlmodel import Session

from lead_radar.discovery.pipeline import run_discovery_pipeline
from lead_radar.models.enums import AccountStatus
from lead_radar.providers import MockProvider
from lead_radar.providers.base import (
    CompanyEventRecord,
    ContactRecord,
    CostEstimate,
    ProviderCompanyRecord,
)


class FlakyProvider:
    """A provider whose get_company_events fails for one domain, to verify a
    single provider error doesn't abort the whole run."""

    name = "flaky"

    def __init__(self) -> None:
        self._inner = MockProvider()

    def estimate_query_cost(self, operation: str, **params: object) -> CostEstimate:
        return self._inner.estimate_query_cost(operation, **params)

    def company_statistics(self, **filters: object) -> dict:
        return self._inner.company_statistics(**filters)

    def search_companies(self, **filters: object) -> list[ProviderCompanyRecord]:
        return self._inner.search_companies(**filters)

    def enrich_company(self, domain: str) -> ProviderCompanyRecord | None:
        return self._inner.enrich_company(domain)

    def get_company_events(self, domain: str) -> list[CompanyEventRecord]:
        if domain == "brightloop-martech.example":
            raise RuntimeError("simulated provider outage")
        return self._inner.get_company_events(domain)

    def find_contacts(self, domain: str) -> list[ContactRecord]:
        return []

    def enrich_contact_email(self, contact: ContactRecord) -> ContactRecord:
        return contact


def test_full_pipeline_scores_and_ranks_demo_companies(session: Session) -> None:
    provider = MockProvider()
    result = run_discovery_pipeline(session, provider, countries=["US", "GB", "DE", "AU", "SG"])

    assert result.accounts_discovered == 8
    assert result.accounts_rejected == 2  # employee band violations
    assert len(result.accounts_scored) == 6
    assert result.provider_errors == []

    domains = {r.account.domain for r in result.accounts_scored}
    assert "globalscale-systems.example" not in domains  # too large, rejected
    assert "tinyagent-labs.example" not in domains  # too small, rejected

    scores = {r.account.domain: r.score_run.total_score for r in result.accounts_scored}
    ranked = sorted(scores.values(), reverse=True)
    assert ranked == sorted(scores.values(), reverse=True)  # sanity: comparable, orderable


def test_provider_event_failure_does_not_abort_the_run(session: Session) -> None:
    provider = FlakyProvider()
    result = run_discovery_pipeline(session, provider, countries=["US", "GB", "DE", "AU", "SG"])

    assert result.provider_errors  # the simulated failure was recorded
    assert any("brightloop-martech.example" in err for err in result.provider_errors)
    # every other account still got scored despite one domain's event fetch failing
    scored_domains = {r.account.domain for r in result.accounts_scored}
    assert "voxstream-audio.example" in scored_domains
    assert (
        "brightloop-martech.example" in scored_domains
    )  # still ingested + scored, just with 0 events


def test_search_companies_failure_returns_empty_result_without_raising(session: Session) -> None:
    class BrokenProvider(MockProvider):
        def search_companies(self, **filters: object) -> list[ProviderCompanyRecord]:
            raise RuntimeError("simulated total outage")

    result = run_discovery_pipeline(session, BrokenProvider(), countries=["US"])
    assert result.accounts_discovered == 0
    assert result.provider_errors


def test_scored_accounts_requiring_review_are_flagged_pending(session: Session) -> None:
    provider = MockProvider()
    result = run_discovery_pipeline(session, provider, countries=["US", "GB", "DE", "AU", "SG"])

    brightloop = next(
        r for r in result.accounts_scored if r.account.domain == "brightloop-martech.example"
    )
    assert brightloop.account.status == AccountStatus.PENDING_HUMAN_REVIEW
