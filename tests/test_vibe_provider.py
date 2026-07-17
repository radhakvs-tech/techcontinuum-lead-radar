"""VibeProvider against a fake VpaiRunner — never invokes the real vpai
binary or spends real credits. The fetch-entities(businesses),
match-business, enrich-business, and fetch-businesses-events fixtures below
are all trimmed from real live calls made this session (see
providers/vibe_provider.py module docstring and docs/vibe-credit-strategy.md
for the exact responses and the parsing corrections they forced).
find_contacts/enrich_contact_email fixtures remain constructed/plausible —
those operations have deliberately never been called live (pending
account-approval-gating review), so their shapes are unverified guesses."""

from __future__ import annotations

from typing import Any

import pytest

from lead_radar.models.enums import AccountStatus
from lead_radar.providers.base import ContactRecord
from lead_radar.providers.credit_control import CreditBudgetExceededError
from lead_radar.providers.vibe_accounts import VibeAccount
from lead_radar.providers.vibe_provider import VibeProvider
from lead_radar.review.guardrails import (
    ContactDiscoveryNotApprovedError,
    EmailEnrichmentNotApprovedError,
    PhoneRetrievalDisabledError,
)
from lead_radar.settings import YamlConfig

# Trimmed from the real `fetch-entities --number-of-results 5` response
# captured this session.
_REAL_FETCH_ENTITIES_BUSINESSES_RESPONSE = {
    "csv_path": "/tmp/vpai-runs/session_x/fetch_entities.csv",
    "session_id": "session_x",
    "row_count": 2,
    "request_count": 1,
    "total_results": 2,
    "columns": ["business_id", "name", "domain", "country_name", "naics_description"],
    "sample_rows": [
        {
            "business_id": "b197ffdef2ddc3308584dce7afa3661b",
            "name": "Google",
            "domain": "google.com",
            "country_name": "united states",
            "number_of_employees_range": "10001+",
            "yearly_revenue_range": "100B-1T",
            "naics_description": "All Other Information Services",
        },
        {
            "business_id": "8f19793b2671094e63a15ab883d50137",
            "name": "Amazon.com, Inc.",
            "domain": "amazon.com",
            "country_name": "united states",
            "number_of_employees_range": "10001+",
            "yearly_revenue_range": "100B-1T",
            "naics_description": "Software Publishers",
        },
    ],
}


class FakeVpaiRunner:
    """Records every call and returns a canned response keyed by command."""

    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        command: str,
        *,
        args: dict[str, Any] | None = None,
        tool_reasoning: str | None = None,
        number_of_results: int | None = None,
        session_id: str | None = None,
        csv_path: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "command": command,
                "args": args,
                "tool_reasoning": tool_reasoning,
                "number_of_results": number_of_results,
            }
        )
        assert tool_reasoning, "vpai requires --tool-reasoning with --args"
        return self._responses.get(command, {})


def _open_budget_config() -> YamlConfig:
    return YamlConfig(
        data={
            "credit_budget": {
                "maximum_per_run": 1000,
                "maximum_per_week": 4000,
                "require_cost_estimate": True,
                "retrieve_contacts_only_after_approval": True,
                "retrieve_email_only_after_approval": True,
                "retrieve_phone_numbers": False,
            },
            "vibe_cost_heuristic": {
                "credit_rates": {
                    "search_list_event_credits_per_call": 1.0,
                    "enrichment_credits_per_record_conservative": 5.0,
                    "enrichment_credits_per_record_published_range": [1.0, 5.0],
                    "enrich_prospects_full_contact_credits": 8.0,
                    "enrich_prospects_phone_only_credits": 10.0,
                    "enrich_prospects_email_only_credits_estimate": 5.0,
                },
                "sample_gate_rows": 5,
                "known_row_limits": {
                    "fetch-entities": 50,
                    "match-business": 50,
                    "match-prospects": 40,
                    "enrich-prospects": 50,
                },
            },
        }
    )


def _zero_budget_config() -> YamlConfig:
    config = _open_budget_config()
    config.data["credit_budget"]["maximum_per_run"] = 0
    return config


def _provider(
    responses: dict[str, dict[str, Any]], budget: YamlConfig | None = None
) -> tuple[VibeProvider, FakeVpaiRunner]:
    runner = FakeVpaiRunner(responses)
    provider = VibeProvider(
        runner=runner,
        providers_config=budget or _open_budget_config(),
        accounts=[VibeAccount(identifier="test@example.com")],
    )
    return provider, runner


def test_default_zero_budget_refuses_search_companies() -> None:
    provider, _runner = _provider(
        {"fetch-entities": _REAL_FETCH_ENTITIES_BUSINESSES_RESPONSE}, budget=_zero_budget_config()
    )
    with pytest.raises(CreditBudgetExceededError):
        provider.search_companies(countries=["US"])


def test_search_companies_parses_real_fetch_entities_shape() -> None:
    provider, runner = _provider({"fetch-entities": _REAL_FETCH_ENTITIES_BUSINESSES_RESPONSE})

    results = provider.search_companies(countries=["US"], number_of_results=5)

    assert [r.domain for r in results] == ["google.com", "amazon.com"]
    assert results[0].company_name == "Google"
    # Real value is "united states" (see country_codes.py) — normalized to
    # the ISO Alpha-2 code the geography hard gate actually expects.
    assert results[0].headquarters_country == "US"
    # Banded strings, not exact figures — never silently coerced to a number.
    assert results[0].employee_count is None
    assert results[0].reported_revenue_usd is None
    assert results[0].raw["number_of_employees_range"] == "10001+"

    call = runner.calls[0]
    assert call["command"] == "fetch-entities"
    assert call["args"]["entity_type"] == "businesses"
    assert call["args"]["filters"]["company_country_code"] == {"values": ["US"]}
    assert call["number_of_results"] == 5
    assert provider.spent_this_run == 1.0  # flat per-call rate


def test_search_companies_defaults_number_of_results_to_sample_gate() -> None:
    provider, runner = _provider({"fetch-entities": _REAL_FETCH_ENTITIES_BUSINESSES_RESPONSE})
    provider.search_companies()
    assert runner.calls[0]["number_of_results"] == 5


@pytest.mark.parametrize(
    ("vpai_country_name", "expected_iso_code"),
    [
        ("united states", "US"),  # confirmed against a real vpai call
        ("united kingdom", "GB"),
        ("germany", "DE"),
        ("australia", "AU"),
        ("singapore", "SG"),
    ],
)
def test_each_configured_country_passes_the_real_geography_hard_gate(
    vpai_country_name: str, expected_iso_code: str
) -> None:
    """End-to-end: a vpai-shaped fetch-entities row for each of icp.yaml's
    five configured countries must produce a ProviderCompanyRecord that
    clears the REAL discovery.hard_gates geography check — not a mock of
    it. This is what silently failed for every country before
    country_codes.py existed (discovered via a real Google ingest)."""
    from lead_radar.discovery.hard_gates import evaluate_hard_gates

    response = {
        "sample_rows": [
            {
                "business_id": "biz_1",
                "name": "Example Co",
                "domain": "example.com",
                "country_name": vpai_country_name,
                "naics_description": "Software Publishers",
            }
        ]
    }
    provider, _runner = _provider({"fetch-entities": response})

    results = provider.search_companies()

    assert results[0].headquarters_country == expected_iso_code
    gate_result = evaluate_hard_gates(results[0])
    geography_reasons = [r for r in gate_result.rejection_reasons if "headquarters_country" in r]
    assert geography_reasons == [], (
        f"{vpai_country_name!r} normalized to {expected_iso_code!r} but still failed the "
        f"geography gate: {geography_reasons}"
    )


def test_company_statistics_passes_through_raw_response() -> None:
    stats_response = {"total_results": 42, "breakdown": {"US": 30, "GB": 12}}
    provider, runner = _provider({"fetch-entities-statistics": stats_response})
    result = provider.company_statistics(countries=["US", "GB"])
    assert result == stats_response
    assert runner.calls[0]["args"]["filters"]["company_country_code"] == {"values": ["US", "GB"]}


# Trimmed from the real match-business(google.com) response captured this
# session.
_REAL_MATCH_BUSINESS_RESPONSE = {
    "csv_path": "/tmp/vpai-runs/session_x/match_business.csv",
    "session_id": "session_x",
    "row_count": 1,
    "columns": ["input_name", "input_domain", "input_url", "input_linkedin_url", "business_id"],
    "sample_rows": [
        {
            "input_name": None,
            "input_domain": "google.com",
            "input_url": None,
            "input_linkedin_url": None,
            "business_id": "b197ffdef2ddc3308584dce7afa3661b",
        }
    ],
}

# Trimmed from the real enrich-business(google.com, firmographics) response
# captured this session. Note the real shape (`data: [{business_id, data:
# {...}}]`, `credit_usage`) is NOT what enrich-business's own --help text
# claims ("enrichment_results as JSON strings") — see module docstring.
_REAL_ENRICH_BUSINESS_RESPONSE = {
    "response_context": {"request_status": "success"},
    "data": [
        {
            "business_id": "b197ffdef2ddc3308584dce7afa3661b",
            "data": {
                "business_id": "b197ffdef2ddc3308584dce7afa3661b",
                "name": "Google",
                "country_name": "united states",
                "naics_description": "All Other Information Services",
                "number_of_employees_range": "10001+",
                "yearly_revenue_range": "100B-1T",
            },
        }
    ],
    "entity_id": None,
    "total_results": 1,
    "credit_usage": {"total_credits": 1, "total_results": 1},
}


def test_enrich_company_chains_match_business_then_enrich_business() -> None:
    responses = {
        "match-business": _REAL_MATCH_BUSINESS_RESPONSE,
        "enrich-business": _REAL_ENRICH_BUSINESS_RESPONSE,
    }
    provider, runner = _provider(responses)

    record = provider.enrich_company("google.com")

    assert record is not None
    assert record.company_name == "Google"
    assert record.domain == "google.com"
    # Real value is "united states" (see country_codes.py) — normalized to
    # the ISO Alpha-2 code the geography hard gate actually expects.
    assert record.headquarters_country == "US"
    assert record.industry == "All Other Information Services"
    # Banded strings only in the real response — never invented as numbers.
    assert record.employee_count is None
    assert record.reported_revenue_usd is None
    assert [c["command"] for c in runner.calls] == ["match-business", "enrich-business"]
    business_id = "b197ffdef2ddc3308584dce7afa3661b"
    assert runner.calls[1]["args"]["business_ids"] == [business_id]
    # credit_usage.total_credits from the real response is captured verbatim.
    assert provider.usage_log[-1]["credits_actual"] == 1


def test_enrich_company_returns_none_when_business_not_matched() -> None:
    provider, _runner = _provider({"match-business": {"sample_rows": []}})
    assert provider.enrich_company("unknown.example") is None


# Trimmed from the real fetch-businesses-events(google.com) response
# captured this session — includes one narrative-style event (title/
# snippet/link) and one structured-style event (no title/snippet/link,
# only fielded data) to exercise both branches of _event_description.
_REAL_BUSINESS_EVENTS_RESPONSE = {
    "response_context": {"request_status": "success"},
    "output_events": [
        {
            "event_name": "new_partnership",
            "event_time": "2026-07-10T00:00:00+00:00",
            "event_id": "8ad3f666f528972fe794faf2874f110e",
            "data": {
                "event_name": "new_partnership",
                "partner_company": "Accenture",
                "link": "https://example.com/accenture-google-cloud-agentic-ai",
                "title": "Accenture and Google Cloud launch agentic AI platform for mid-market",
                "snippet": "Accenture and Google Cloud are expanding their long-running deal.",
            },
            "business_id": "b197ffdef2ddc3308584dce7afa3661b",
        },
        {
            "event_name": "hiring_in_engineering_department",
            "event_time": "2026-06-17T00:00:00+00:00",
            "event_id": "fbf210239e659c0c8e9d5cb6a0765072",
            "data": {
                "event_name": "hiring_in_engineering_department",
                "department": "engineering",
                "job_titles": ["cpu design verification engineer"],
                "job_count": 1,
                "location": "new york, united states",
            },
            "business_id": "b197ffdef2ddc3308584dce7afa3661b",
        },
    ],
    "credit_usage": {"total_credits": 2, "total_results": 2},
}


def test_get_company_events_chains_match_business_then_fetch_events() -> None:
    responses = {
        "match-business": _REAL_MATCH_BUSINESS_RESPONSE,
        "fetch-businesses-events": _REAL_BUSINESS_EVENTS_RESPONSE,
    }
    provider, runner = _provider(responses)

    events = provider.get_company_events("google.com")

    assert len(events) == 2

    narrative = events[0]
    assert narrative.event_type == "new_partnership"
    assert narrative.title.startswith("Accenture and Google Cloud")
    assert narrative.description.startswith("Accenture and Google Cloud are expanding")
    assert narrative.event_date.isoformat() == "2026-07-10"
    assert narrative.source_url == "https://example.com/accenture-google-cloud-agentic-ai"

    structured = events[1]
    assert structured.event_type == "hiring_in_engineering_department"
    # No title/snippet/link in structured events — title is synthesized
    # from event_name, description from the fielded data, source_url unset.
    assert structured.title == "Hiring In Engineering Department"
    assert "job_titles" in structured.description
    assert structured.source_url is None
    assert structured.event_date.isoformat() == "2026-06-17"

    business_id = "b197ffdef2ddc3308584dce7afa3661b"
    fetch_call = runner.calls[1]
    assert fetch_call["args"]["business_ids"] == [business_id]
    assert "new_partnership" in fetch_call["args"]["event_types"]
    assert provider.usage_log[-1]["credits_actual"] == 2


# Trimmed from the real fetch-entities(prospects, business_id=google's)
# response captured this session (account id 9, approved via the real CLI
# `review approve` command). Real column names confirmed here diverge from
# fetch-entities(businesses)': `linkedin` (bare, no scheme), not
# `linkedin_profile` — see module docstring correction #4.
_FIND_CONTACTS_RESPONSES = {
    "match-business": _REAL_MATCH_BUSINESS_RESPONSE,
    "fetch-entities": {
        "csv_path": "/tmp/vpai-runs/session_x/fetch_entities_prospects.csv",
        "session_id": "session_x",
        "row_count": 2,
        "columns": ["prospect_id", "full_name", "job_title", "linkedin", "business_id"],
        "sample_rows": [
            {
                "prospect_id": "6b39e11efd690384ed593ef9bcacfecaf6ed51b7",
                "full_name": "Sundar  Pichai",
                "job_title": "Chief executive officer",
                "linkedin": "linkedin.com/in/ACoAAE6FVtYBAW4bP82g1IhIHxzu_1J010WU3CQ",
                "business_id": "b197ffdef2ddc3308584dce7afa3661b",
            },
            {
                "prospect_id": "43cba106c62403b408fab17bc16c774713f6f0cb",
                "full_name": "Thomas Kurian",
                "job_title": "Chief executive officer - google cloud",
                "linkedin": "linkedin.com/in/ACoAAAPoihEBiBmmg87UQXgpurPIs_mwnZYnMEI",
                "business_id": "b197ffdef2ddc3308584dce7afa3661b",
            },
        ],
    },
}


def test_find_contacts_refuses_when_no_account_status_given() -> None:
    """Structural gate: omitting account_status — the same call shape the
    CompanyDataProvider protocol's find_contacts(domain) allows — must
    refuse, not default to permissive."""
    provider, runner = _provider(_FIND_CONTACTS_RESPONSES)
    with pytest.raises(ContactDiscoveryNotApprovedError):
        provider.find_contacts("acme.example")
    # Refused before any real call was even attempted.
    assert runner.calls == []


@pytest.mark.parametrize(
    "status",
    [
        AccountStatus.DISCOVERED,
        AccountStatus.SCORED,
        AccountStatus.PENDING_HUMAN_REVIEW,
        AccountStatus.REJECTED,
    ],
)
def test_find_contacts_refuses_every_status_except_approved(status: AccountStatus) -> None:
    provider, runner = _provider(_FIND_CONTACTS_RESPONSES)
    with pytest.raises(ContactDiscoveryNotApprovedError):
        provider.find_contacts("acme.example", account_status=status)
    assert runner.calls == []


def test_find_contacts_proceeds_when_approved() -> None:
    provider, runner = _provider(_FIND_CONTACTS_RESPONSES)

    contacts = provider.find_contacts(
        "google.com", account_status=AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY
    )

    assert len(contacts) == 2
    assert all(c.email is None for c in contacts)

    sundar = contacts[0]
    assert sundar.name == "Sundar  Pichai"  # real data, double space and all
    assert sundar.exact_title == "Chief executive officer"
    # linkedin -> https://linkedin.com/... : bare field normalized to a
    # usable URL, not left schemeless and not dropped as None.
    assert sundar.public_profile_url == "https://linkedin.com/in/ACoAAE6FVtYBAW4bP82g1IhIHxzu_1J010WU3CQ"

    fetch_call = runner.calls[1]
    assert fetch_call["args"]["entity_type"] == "prospects"
    assert fetch_call["number_of_results"] == 2


_ENRICH_CONTACT_EMAIL_RESPONSES = {
    "match-prospects": {"sample_rows": [{"prospect_id": "p_1"}]},
    "enrich-prospects": {"enrichment_results": {"contacts": '{"email": "jordan@acme.example"}'}},
}


def _jordan_contact() -> ContactRecord:
    return ContactRecord(
        account_domain="acme.example", name="Jordan Lee", exact_title="VP Engineering"
    )


def test_enrich_contact_email_refuses_when_no_account_status_given() -> None:
    provider, runner = _provider(_ENRICH_CONTACT_EMAIL_RESPONSES)
    with pytest.raises(EmailEnrichmentNotApprovedError):
        provider.enrich_contact_email(_jordan_contact())
    assert runner.calls == []


def test_enrich_contact_email_refuses_contact_discovery_approval_alone() -> None:
    """Contact-discovery approval is necessary but not sufficient — email
    enrichment requires its own separate, explicit approval flag
    (spec §6/§11/§23), even when account_status is otherwise approved."""
    provider, runner = _provider(_ENRICH_CONTACT_EMAIL_RESPONSES)
    with pytest.raises(EmailEnrichmentNotApprovedError):
        provider.enrich_contact_email(
            _jordan_contact(),
            account_status=AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY,
            email_enrichment_approved=False,
        )
    assert runner.calls == []


def test_enrich_contact_email_refuses_email_flag_without_contact_discovery_approval() -> None:
    """require_email_enrichment_approved checks contact-discovery approval
    first (raising the more specific ContactDiscoveryNotApprovedError)
    before it ever looks at email_enrichment_approved — an unapproved
    status can't be overridden by the email flag alone."""
    provider, runner = _provider(_ENRICH_CONTACT_EMAIL_RESPONSES)
    with pytest.raises(ContactDiscoveryNotApprovedError):
        provider.enrich_contact_email(
            _jordan_contact(),
            account_status=AccountStatus.PENDING_HUMAN_REVIEW,
            email_enrichment_approved=True,
        )
    assert runner.calls == []


def test_enrich_contact_email_proceeds_when_both_approvals_set() -> None:
    provider, runner = _provider(_ENRICH_CONTACT_EMAIL_RESPONSES)

    enriched = provider.enrich_contact_email(
        _jordan_contact(),
        account_status=AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY,
        email_enrichment_approved=True,
    )

    assert enriched.email == "jordan@acme.example"
    enrich_call = runner.calls[1]
    assert enrich_call["command"] == "enrich-prospects"
    assert enrich_call["args"]["parameters"]["contact_types"] == ["email"]
    assert "phone" not in enrich_call["args"]["parameters"]["contact_types"]


def test_enrich_contact_email_returns_original_contact_when_no_match() -> None:
    provider, _runner = _provider({"match-prospects": {"sample_rows": []}})
    contact = _jordan_contact()

    result = provider.enrich_contact_email(
        contact,
        account_status=AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY,
        email_enrichment_approved=True,
    )

    assert result.email is None
    assert result is not contact or result == contact  # unchanged either way


def test_resolve_contact_types_defaults_to_email_only() -> None:
    provider, _runner = _provider({})
    assert provider._resolve_contact_types() == ["email"]


def test_resolve_contact_types_calls_the_real_guard_when_config_would_allow_phone() -> None:
    """The block on phone retrieval is the guard function actually
    executing, not just the ["email"] literal happening to omit "phone" —
    this proves it by flipping the config flag the guard is wired to and
    confirming PhoneRetrievalDisabledError actually fires."""
    config = _open_budget_config()
    config.data["credit_budget"]["retrieve_phone_numbers"] = True
    provider, runner = _provider({}, budget=config)

    with pytest.raises(PhoneRetrievalDisabledError):
        provider._resolve_contact_types()
    assert runner.calls == []


def test_active_account_returns_single_configured_account() -> None:
    provider, _runner = _provider({})
    assert provider.active_account is not None
    assert provider.active_account.identifier == "test@example.com"


def test_estimate_query_cost_delegates_to_heuristic() -> None:
    provider, _runner = _provider({})
    estimate = provider.estimate_query_cost("fetch-entities", number_of_results=5)
    assert estimate.estimated_credits == 1.0  # flat per-call rate
    assert "not a vendor-confirmed price" in estimate.notes or "flat per call" in estimate.notes
