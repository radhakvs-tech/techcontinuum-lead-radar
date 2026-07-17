"""Local, heuristic query-cost estimation for the future VibeProvider.
Spec §6 ("estimate cost where supported").

`vpai` — the real Vibe Prospecting CLI — has no account-balance,
credit-usage, or cost-estimate API. This was confirmed three ways, not
assumed:

- `vpai whoami` returns only auth status (authenticated, auth_source,
  api_key_hint, oauth token/expiry fields) — nothing about credits, balance,
  or usage.
- Every subcommand's `--help` and `--all-parameters` (the full MCP
  inputSchema) was inspected; no command or field anywhere mentions credit,
  balance, usage, quota, billing, or account standing.
- One real live call was made (`fetch-entities --number-of-results 5`) and
  its raw JSON response inspected end to end: `csv_path`, `session_id`,
  `row_count`, `request_count`, `total_results`, `columns`, `sample_rows` —
  no cost/credit/balance field appeared that wasn't already visible in the
  documented schema.
- The only real, vendor-provided bounded-cost control found is
  `fetch-entities --number-of-results`, documented as defaulting to 50 rows
  with a "Sample gate: 5" — capping a request at 5 rows is the one
  mechanism the vendor actually gives us to bound spend before a full-size
  call.

See docs/vibe-credit-strategy.md for the full writeup, including the
published Explorium credit-rate figures this module uses
(config/providers.yaml `vibe_cost_heuristic.credit_rates`) — real published
numbers (explorium.ai/pricing, explorium.ai blog, third-party comparison
reviews), but NOT vendor-API-confirmed, since no such API exists. Every
`CostEstimate` this produces says so in `notes`. Callers building
VibeProvider should treat it only as a size/spend check ahead of running
the real `--number-of-results 5` sample gate — the one dry run that
actually costs what the vendor says it costs, rather than what we estimate
it costs.
"""

from __future__ import annotations

from typing import Any

from lead_radar.providers.base import CostEstimate
from lead_radar.settings import YamlConfig, get_providers_config

# "Generate/search/list/event actions: 1 credit" (published), read as a
# flat per-call rate rather than per-row — see module docstring and
# config/providers.yaml for the caveat on that interpretation.
_FLAT_PER_CALL_OPERATIONS = {
    "fetch-entities",
    "match-business",
    "match-prospects",
    "fetch-entities-statistics",
    "fetch-businesses-events",
    "fetch-prospects-events",
    "autocomplete",
}

# Row/id-count context to report alongside the flat per-call operations
# above, purely informational (doesn't change estimated_credits under our
# flat-rate interpretation).
_ROW_COUNT_PARAM_BY_OPERATION: dict[str, str] = {
    "fetch-entities": "number_of_results",
    "match-business": "businesses_to_match",
    "match-prospects": "prospects_to_match",
    "fetch-businesses-events": "business_ids",
    "fetch-prospects-events": "prospect_ids",
}

_PUBLISHED_SOURCE_NOTE = (
    "published Explorium rate (explorium.ai/pricing / blog / third-party "
    "reviews, 2026-07-17) — NOT vendor-API-confirmed, since vpai exposes no "
    "cost API."
)


def _flat_per_call_estimate(
    operation: str, rate: float, known_limits: dict[str, int], params: dict[str, Any]
) -> CostEstimate:
    size_param = _ROW_COUNT_PARAM_BY_OPERATION.get(operation)
    size_note = ""
    if size_param is not None:
        raw = params.get(size_param)
        if isinstance(raw, list):
            size_note = f" ({len(raw)} '{size_param}' entries requested)"
        elif raw is not None:
            cap = known_limits.get(operation)
            size_note = f" ({raw} rows requested, vendor default/cap {cap})"
    return CostEstimate(
        operation=operation,
        estimated_credits=rate,
        notes=(
            f"{rate:g} credit flat per call — {_PUBLISHED_SOURCE_NOTE} Interpreted as "
            f"per-call, not per-row (the published phrasing doesn't say which).{size_note} "
            "For fetch-entities specifically, still prefer running "
            "--number-of-results 5 (vpai's documented Sample Gate) first as the real "
            "bounded-cost dry run before a full-size fetch."
        ),
    )


def _enrich_business_estimate(rate: float, params: dict[str, Any]) -> CostEstimate:
    business_ids = params.get("business_ids") or []
    enrichments = params.get("enrichments") or []
    enrichment_count = max(len(enrichments), 1)
    credits = len(business_ids) * enrichment_count * rate
    return CostEstimate(
        operation="enrich-business",
        estimated_credits=credits,
        notes=(
            f"{len(business_ids)} business_ids x {enrichment_count} enrichment type(s) x "
            f"{rate:g} credits/record (conservative upper bound of the {_PUBLISHED_SOURCE_NOTE} "
            "'1-5 credits depending on data type' range — no published per-type breakdown "
            "exists). No documented vendor cap on business_ids count for this operation."
        ),
    )


def _enrich_prospects_estimate(
    rates: dict[str, float], known_limits: dict[str, int], params: dict[str, Any]
) -> CostEstimate:
    prospect_ids = params.get("prospect_ids") or []
    cap = known_limits.get("enrich-prospects")
    counted = min(len(prospect_ids), cap) if cap is not None else len(prospect_ids)

    enrichments = set(params.get("enrichments") or [])
    per_prospect_rate = 0.0
    rate_notes: list[str] = []

    if "contacts" in enrichments:
        contact_types = (params.get("parameters") or {}).get("contact_types")
        contact_types_set = set(contact_types) if contact_types else {"email", "phone"}
        if contact_types_set == {"email", "phone"}:
            per_prospect_rate += rates["enrich_prospects_full_contact_credits"]
            rate_notes.append(
                f"contacts (email+phone): {rates['enrich_prospects_full_contact_credits']:g} "
                f"credits/prospect ({_PUBLISHED_SOURCE_NOTE})"
            )
        elif contact_types_set == {"phone"}:
            per_prospect_rate += rates["enrich_prospects_phone_only_credits"]
            rate_notes.append(
                f"contacts (phone only): {rates['enrich_prospects_phone_only_credits']:g} "
                f"credits/prospect ({_PUBLISHED_SOURCE_NOTE})"
            )
        else:
            per_prospect_rate += rates["enrich_prospects_email_only_credits_estimate"]
            rate_notes.append(
                "contacts (email only): "
                f"{rates['enrich_prospects_email_only_credits_estimate']:g} credits/prospect "
                "(OUR extrapolation, NOT a published figure — Explorium only says email is "
                "'cheaper' than the phone rate, with no exact number)"
            )

    if "profiles" in enrichments:
        per_prospect_rate += rates["enrichment_credits_per_record_conservative"]
        rate_notes.append(
            f"profiles: {rates['enrichment_credits_per_record_conservative']:g} "
            f"credits/prospect (conservative upper bound of the {_PUBLISHED_SOURCE_NOTE} "
            "generic 1-5 enrichment range)"
        )

    credits = counted * per_prospect_rate
    cap_note = f"capped at vendor limit {cap}" if len(prospect_ids) != counted else "uncapped"
    return CostEstimate(
        operation="enrich-prospects",
        estimated_credits=credits,
        notes=(
            f"{counted} prospect(s) ({cap_note} from {len(prospect_ids)} requested) x "
            f"{per_prospect_rate:g} credits/prospect. " + "; ".join(rate_notes)
        ),
    )


def estimate_vibe_query_cost(
    operation: str,
    providers_config: YamlConfig | None = None,
    **params: Any,
) -> CostEstimate:
    """Heuristic estimate for a raw vpai tool call, built from Explorium's
    published credit rates (config/providers.yaml `vibe_cost_heuristic`),
    not a vendor API (none exists).

    `operation` is a vpai tool name (e.g. "fetch-entities",
    "enrich-prospects"), not a CompanyDataProvider protocol method — a
    future VibeProvider maps its own protocol methods onto these before
    calling in.
    """
    config = providers_config or get_providers_config()
    heuristic_cfg = config["vibe_cost_heuristic"]
    rates: dict[str, float] = heuristic_cfg["credit_rates"]
    known_limits: dict[str, int] = heuristic_cfg["known_row_limits"]
    sample_gate_rows = int(heuristic_cfg["sample_gate_rows"])

    if operation in _FLAT_PER_CALL_OPERATIONS:
        return _flat_per_call_estimate(
            operation, rates["search_list_event_credits_per_call"], known_limits, params
        )

    if operation == "enrich-business":
        conservative_rate = rates["enrichment_credits_per_record_conservative"]
        return _enrich_business_estimate(conservative_rate, params)

    if operation == "enrich-prospects":
        return _enrich_prospects_estimate(rates, known_limits, params)

    return CostEstimate(
        operation=operation,
        estimated_credits=float(sample_gate_rows)
        * rates["search_list_event_credits_per_call"],
        notes=(
            f"'{operation}' is not in the known vpai operation table — this estimate is "
            "unreliable. Verify with a real sample-gate-sized call before trusting any "
            "number here."
        ),
    )
