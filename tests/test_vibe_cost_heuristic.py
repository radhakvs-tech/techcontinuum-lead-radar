"""Spec §6 'estimate cost where supported'. vpai has no real cost API, so
this heuristic uses Explorium's published credit rates — real numbers, but
not vendor-API-confirmed — to size requests, not to price them precisely.
See docs/vibe-credit-strategy.md and providers/vibe_cost_heuristic.py."""

from __future__ import annotations

from lead_radar.providers.vibe_cost_heuristic import estimate_vibe_query_cost
from lead_radar.settings import YamlConfig

_HEURISTIC_CFG = YamlConfig(
    data={
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
        }
    }
)


def test_search_list_event_operations_are_flat_one_credit_per_call() -> None:
    for operation, params in [
        ("fetch-entities", {"number_of_results": 50}),
        ("fetch-entities", {"number_of_results": 5}),
        ("match-business", {"businesses_to_match": [{"name": "Acme"}, {"name": "Globex"}]}),
        ("fetch-entities-statistics", {}),
        ("autocomplete", {}),
        ("fetch-businesses-events", {"business_ids": ["b1", "b2", "b3"]}),
    ]:
        estimate = estimate_vibe_query_cost(operation, providers_config=_HEURISTIC_CFG, **params)
        assert estimate.estimated_credits == 1.0, operation
        assert "flat per call" in estimate.notes


def test_fetch_entities_still_recommends_sample_gate() -> None:
    estimate = estimate_vibe_query_cost(
        "fetch-entities", providers_config=_HEURISTIC_CFG, number_of_results=50
    )
    assert "Sample Gate" in estimate.notes


def test_enrich_business_scales_with_ids_and_enrichment_types() -> None:
    estimate = estimate_vibe_query_cost(
        "enrich-business",
        providers_config=_HEURISTIC_CFG,
        business_ids=["b1", "b2"],
        enrichments=["firmographics", "technographics"],
    )
    # 2 business_ids x 2 enrichment types x 5.0 conservative rate
    assert estimate.estimated_credits == 20.0
    assert "No documented vendor cap" in estimate.notes


def test_enrich_prospects_full_contact_uses_published_rate() -> None:
    estimate = estimate_vibe_query_cost(
        "enrich-prospects",
        providers_config=_HEURISTIC_CFG,
        prospect_ids=["p1", "p2"],
        enrichments=["contacts"],
        parameters={"contact_types": ["email", "phone"]},
    )
    assert estimate.estimated_credits == 16.0  # 2 prospects x 8 credits
    assert "email+phone" in estimate.notes


def test_enrich_prospects_omitted_contact_types_defaults_to_full_contact_rate() -> None:
    estimate = estimate_vibe_query_cost(
        "enrich-prospects",
        providers_config=_HEURISTIC_CFG,
        prospect_ids=["p1"],
        enrichments=["contacts"],
    )
    assert estimate.estimated_credits == 8.0


def test_enrich_prospects_phone_only_uses_published_higher_rate() -> None:
    estimate = estimate_vibe_query_cost(
        "enrich-prospects",
        providers_config=_HEURISTIC_CFG,
        prospect_ids=["p1"],
        enrichments=["contacts"],
        parameters={"contact_types": ["phone"]},
    )
    assert estimate.estimated_credits == 10.0


def test_enrich_prospects_email_only_is_flagged_as_extrapolation_not_published() -> None:
    estimate = estimate_vibe_query_cost(
        "enrich-prospects",
        providers_config=_HEURISTIC_CFG,
        prospect_ids=["p1"],
        enrichments=["contacts"],
        parameters={"contact_types": ["email"]},
    )
    assert estimate.estimated_credits == 5.0
    assert "NOT a published figure" in estimate.notes


def test_enrich_prospects_contacts_and_profiles_combine() -> None:
    estimate = estimate_vibe_query_cost(
        "enrich-prospects",
        providers_config=_HEURISTIC_CFG,
        prospect_ids=["p1"],
        enrichments=["contacts", "profiles"],
        parameters={"contact_types": ["email", "phone"]},
    )
    # 8 (full contact) + 5 (profiles conservative) = 13 credits for 1 prospect
    assert estimate.estimated_credits == 13.0


def test_enrich_prospects_respects_vendor_cap() -> None:
    estimate = estimate_vibe_query_cost(
        "enrich-prospects",
        providers_config=_HEURISTIC_CFG,
        prospect_ids=[f"p{i}" for i in range(75)],
        enrichments=["contacts"],
        parameters={"contact_types": ["email", "phone"]},
    )
    assert estimate.estimated_credits == 400.0  # capped at 50 prospects x 8 credits
    assert "capped at vendor limit" in estimate.notes


def test_unknown_operation_is_flagged_unreliable_not_silently_zero() -> None:
    estimate = estimate_vibe_query_cost(
        "some-future-tool-not-in-the-table", providers_config=_HEURISTIC_CFG
    )
    assert estimate.estimated_credits > 0.0
    assert "unreliable" in estimate.notes
