"""VibeProvider — CompanyDataProvider backed by the real `vpai` CLI.
Spec §6, §20 (Phase 2).

## What's verified vs. inferred

Real vpai calls made from this codebase so far, all against a single
company (Google, domain google.com) for validation:
`fetch-entities`(businesses, 5-row Sample Gate), `match-business`,
`enrich-business`(firmographics), `fetch-businesses-events`, and now
`fetch-entities`(prospects, via `find_contacts` — one real call, gated
behind a real `AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY` account
approved through the actual CLI review command, spec §10). Their response
shapes are confirmed against real data — see per-function comments below
for exact field names. `enrich_contact_email` (which touches
`match-prospects`, `enrich-prospects`) has deliberately NOT been called
live — pulling a real person's email is its own separate approval, held
back pending explicit go-ahead (spec §6/§11/§23). Its parsing is
unverified guesswork and should not be trusted.

Four corrections already had to be made after real data came back — worth
noting because it means the *documented* schema doesn't always match
reality, even for tools whose docs were read carefully first, and doesn't
even stay consistent tool-to-tool — or entity_type-to-entity_type on the
*same* tool — within vpai itself:

1. `match-business` DOES use the `sample_rows` envelope other list/search
   tools use — this one guess turned out right (row shape: `input_name`,
   `input_domain`, `input_url`, `input_linkedin_url`, `business_id`).
2. `enrich-business`'s own `--help` text says results "come back under
   `enrichment_results` as JSON strings per enrichment key" — that
   describes some other consumption mode (the doc's "Cowork" reference,
   likely a different Explorium product surface), not this CLI's direct
   JSON output. The real shape is `{"data": [{"business_id": ...,
   "data": {...fields...}}], "credit_usage": {"total_credits": N}, ...}`
   — see `_enrich_business_fields`.
3. `fetch-businesses-events` requires `event_types` (a capped array,
   `maxItems: 10`, from a fixed enum) — the docs read as if it could be
   omitted for a default rolling window; it cannot. A first live call
   failed MCP validation before ever reaching Explorium's API. Once fixed,
   its response uses a THIRD, different envelope again: top-level
   `output_events`, each `{event_name, event_time, event_id, data,
   business_id}` — not `sample_rows`, not `enrich-business`'s `data[].data`
   either. Worse, `data`'s inner shape varies *by event type*: narrative
   events (`new_product`, `new_partnership`) carry `title`/`snippet`/
   `link`; structured events (`hiring_in_*_department`, `increase_in_*`)
   carry none of those, only fielded data (`department`, `job_titles`,
   `job_count`, `location`). See `_event_description`.
4. `fetch-entities`(prospects) DOES share the `sample_rows` envelope with
   `fetch-entities`(businesses) — but a prospect row's LinkedIn field is
   named `linkedin` (bare string, no scheme, e.g.
   "linkedin.com/in/..."), not `linkedin_profile` like a business row's
   full `https://...` URL. Same tool, different `entity_type`, different
   field name for the same concept — see `_normalize_linkedin_url`.

So: two of vpai's own tools (`match-business`, `enrich-business`) that
share nearly identical `--help` boilerplate turned out to use two
completely different response envelopes, a third tool
(`fetch-businesses-events`) uses a third envelope with per-event-type
internal variation on top, and even two `entity_type` values of the *same*
tool (`fetch-entities`) name an equivalent field differently. Nothing
about a tool's *documented* similarity to another tool — or to its own
other modes — is evidence of a shared shape. Every operation needs its own
real validation. Treat `enrich_contact_email`'s still-unverified parsing
(intentionally un-called — see above) as no more reliable than a coin flip
until it, too, has been run once for real.

## Credit reporting: partially real, not purely a heuristic guess

`fetch-entities` responses carry no cost field at all (confirmed — see
docs/vibe-credit-strategy.md). But `enrich-business` and
`fetch-businesses-events` responses both included a real
`"credit_usage": {"total_credits": N}` field — actual, vendor-reported
cost for that specific call. So the earlier blanket claim "vpai has no
cost API" was too strong: at least those two self-report real spend after
the fact. This provider now captures that figure into `usage_log` as
`credits_actual` whenever a response includes it, alongside the pre-call
heuristic estimate — see `_record_actual_credits`. It remains a post-hoc
figure, not a pre-call estimate, so `estimate_vibe_query_cost`/
`require_budget` still gate every call *before* it runs.

The two real data points collected so far both diverge from the
heuristic, in both directions — not enough to recalibrate the published
rates from (n=1 each), but worth recording: `enrich-business` with one
`firmographics` enrichment on one business actually cost **1 credit**,
against our conservative 5-credit estimate (the published "1-5 depending
on data type" range's low end, not the high end we assumed).
`fetch-businesses-events` for one business actually cost **2 credits**,
against our flat 1-credit "search/list/event" estimate — so that category
guess undershot by half, at least for this call shape (10 requested event
types). Both remain single data points; do not tighten
`config/providers.yaml credit_rates` from them without more samples.

## Credit safety

Every real vpai call is preceded by `estimate_vibe_query_cost` (published
Explorium rates for pre-call budgeting; see above for the one operation
now known to also self-report actual spend) and
`credit_control.require_budget`, which raises `CreditBudgetExceededError`
whenever projected spend would exceed `config/providers.yaml`
`credit_budget.maximum_per_run` — 0 by default, so every method on this
class refuses to spend anything until a human explicitly raises that
limit. This is defense in depth, not a substitute for care: nothing in
this file should be pointed at a live account without the caller having
deliberately raised the budget first.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from lead_radar.models.enums import AccountStatus
from lead_radar.providers.base import (
    CompanyEventRecord,
    ContactRecord,
    CostEstimate,
    ProviderCompanyRecord,
)
from lead_radar.providers.country_codes import normalize_country_to_iso_alpha2
from lead_radar.providers.credit_control import require_budget
from lead_radar.providers.vibe_accounts import (
    VibeAccount,
    load_configured_accounts,
    select_next_account,
)
from lead_radar.providers.vibe_cost_heuristic import estimate_vibe_query_cost
from lead_radar.providers.vpai_runner import CachingVpaiRunner, SubprocessVpaiRunner, VpaiRunner
from lead_radar.review.guardrails import (
    ContactDiscoveryNotApprovedError,
    EmailEnrichmentNotApprovedError,
    guard_phone_retrieval_call,
    require_contact_discovery_approved,
    require_email_enrichment_approved,
)
from lead_radar.settings import YamlConfig, get_providers_config, get_settings

# fetch-businesses-events requires `event_types` (discovered via a failed
# real call — its --help text reads as if a default rolling window applies
# with event_types omitted; it does not, and the call is rejected by MCP
# input validation before reaching Explorium's API). Confirmed enum values
# via `vpai fetch-businesses-events --all-parameters` (schema-only, not a
# billed call). `maxItems: 10` caps how many can be requested at once — this
# default picks the 10 most relevant to spec §4's signal taxonomy (funding,
# product/partnership activity, engineering hiring, M&A, security, cost
# pressure) rather than an arbitrary subset of the 38 available.
DEFAULT_BUSINESS_EVENT_TYPES = [
    "new_funding_round",
    "new_investment",
    "new_product",
    "new_partnership",
    "merger_and_acquisitions",
    "increase_in_engineering_department",
    "hiring_in_engineering_department",
    "cost_cutting",
    "outages_and_security_breaches",
    "ipo_announcement",
]


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _normalize_linkedin_url(value: Any) -> str | None:
    """CONFIRMED (real call, module docstring): fetch-entities(prospects)'
    `linkedin` field is a bare string with no scheme (e.g.
    "linkedin.com/in/..."), unlike fetch-entities(businesses)'
    `linkedin_profile`, which is a full https:// URL. Normalized here so
    ContactRecord.public_profile_url is consistently a usable URL either
    way, rather than leaking the schemeless form."""
    if not value:
        return None
    text = str(value)
    if text.startswith(("http://", "https://")):
        return text
    return f"https://{text}"


class VibeProvider:
    """CompanyDataProvider backed by the real Vibe Prospecting CLI (`vpai`)."""

    name = "vibe"

    def __init__(
        self,
        runner: VpaiRunner | None = None,
        providers_config: YamlConfig | None = None,
        accounts: list[VibeAccount] | None = None,
    ) -> None:
        self._providers_config = providers_config or get_providers_config()
        self._runner: VpaiRunner = runner or CachingVpaiRunner(SubprocessVpaiRunner())
        if accounts is not None:
            self._accounts = accounts
        else:
            self._accounts = load_configured_accounts(get_settings().vibe_account_emails)
        self._spent_this_run = 0.0
        self.usage_log: list[dict[str, Any]] = []

    @property
    def spent_this_run(self) -> float:
        return self._spent_this_run

    @property
    def active_account(self) -> VibeAccount | None:
        """Which locally-tracked account priority selection would spend
        from next (soonest-expiry-first — see providers/vibe_accounts.py).
        Informational only: vpai's own OAuth session from `vpai login`
        determines which account a call actually executes against, and
        this codebase has no mechanism yet to switch vpai's live
        credentials per account (see docs/vibe-credit-strategy.md)."""
        return select_next_account(self._accounts)

    def _sample_gate_rows(self) -> int:
        return int(self._providers_config["vibe_cost_heuristic"]["sample_gate_rows"])

    def estimate_query_cost(self, operation: str, **params: Any) -> CostEstimate:
        return estimate_vibe_query_cost(
            operation, providers_config=self._providers_config, **params
        )

    def _spend(self, operation: str, **estimate_params: Any) -> CostEstimate:
        estimate = self.estimate_query_cost(operation, **estimate_params)
        require_budget(estimate.estimated_credits, self._spent_this_run, self._providers_config)
        self._spent_this_run += estimate.estimated_credits
        self.usage_log.append(
            {
                "operation": operation,
                "estimated_credits": estimate.estimated_credits,
                "notes": estimate.notes,
            }
        )
        return estimate

    # -- response parsing -----------------------------------------------

    def _rows(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """`sample_rows` is confirmed for fetch-entities(businesses); for
        every other operation this is the inferred-not-confirmed envelope
        described in the module docstring."""
        return list(response.get("sample_rows") or [])

    def _enrich_business_fields(self, response: dict[str, Any]) -> dict[str, Any]:
        """CONFIRMED shape (real `enrich-business` call, see module
        docstring): `{"data": [{"business_id": ..., "data": {...fields...}}],
        "credit_usage": {"total_credits": N}, ...}`. The tool's own --help
        text claims a different `enrichment_results`-as-JSON-string shape;
        that turned out to describe a different consumption mode, not this
        CLI's actual JSON output — see module docstring point 1."""
        entries = response.get("data") or []
        if not entries:
            return {}
        fields = entries[0].get("data")
        return fields if isinstance(fields, dict) else {}

    def _enrichment_result(self, response: dict[str, Any], key: str) -> dict[str, Any]:
        """UNVERIFIED for enrich-prospects (never called live — see module
        docstring). This was also the assumed shape for enrich-business,
        which turned out wrong once tested for real
        (`_enrich_business_fields` now handles that tool instead); treat
        this function's output as similarly unreliable until
        enrich-prospects has its own real validation call."""
        raw = (response.get("enrichment_results") or {}).get(key)
        if not raw:
            return {}
        if isinstance(raw, str):
            parsed: dict[str, Any] = json.loads(raw)
            return parsed
        if isinstance(raw, dict):
            return raw  # tolerate an already-parsed dict too
        return {}

    def _record_actual_credits(self, response: dict[str, Any]) -> None:
        """Some vpai responses self-report real spend after the fact via
        `credit_usage.total_credits` (confirmed on `enrich-business` — see
        module docstring). When present, attach it to the most recent
        usage_log entry as `credits_actual`, alongside the pre-call
        heuristic estimate already recorded by `_spend`."""
        credits_actual = (response.get("credit_usage") or {}).get("total_credits")
        if credits_actual is not None and self.usage_log:
            self.usage_log[-1]["credits_actual"] = credits_actual

    def _row_to_company_record(self, row: dict[str, Any]) -> ProviderCompanyRecord:
        """Field names verified against one real fetch-entities(businesses)
        response (docs/vibe-credit-strategy.md). employee_count and
        reported_revenue_usd are left unset: vpai only returns banded
        strings (`number_of_employees_range`, `yearly_revenue_range`), not
        exact figures. Mapping those bands to numeric estimates is a
        separate, deliberate modelling decision — not done implicitly
        here; the raw strings are preserved in `raw` for that future work.
        """
        return ProviderCompanyRecord(
            company_name=row.get("name", ""),
            domain=row.get("domain", ""),
            # vpai returns a free-text name ("united states"); hard gates
            # expect ISO Alpha-2 ("US") — see country_codes.py module
            # docstring for why this normalization exists.
            headquarters_country=normalize_country_to_iso_alpha2(row.get("country_name")),
            employee_count=None,
            reported_revenue_usd=None,
            industry=row.get("naics_description"),
            business_model=None,
            company_type=None,
            technologies=[],
            raw=row,
        )

    def _match_business_id(self, domain: str) -> str | None:
        """CONFIRMED (real match-business call against google.com, see
        module docstring): shares fetch-entities' `sample_rows` envelope,
        each row carrying `business_id` — matched the real `business_id`
        already seen from fetch-entities for the same company exactly."""
        match_args = {"businesses_to_match": [{"domain": domain}]}
        self._spend("match-business", businesses_to_match=match_args["businesses_to_match"])
        response = self._runner.run(
            "match-business",
            args=match_args,
            tool_reasoning=f"Look up the Explorium business ID for {domain}.",
        )
        self._record_actual_credits(response)
        rows = self._rows(response)
        if not rows:
            return None
        business_id = rows[0].get("business_id") or rows[0].get("id")
        return str(business_id) if business_id is not None else None

    # -- CompanyDataProvider protocol ------------------------------------

    def company_statistics(self, **filters: Any) -> dict[str, Any]:
        entity_type = filters.pop("entity_type", "businesses")
        vpai_filters = dict(filters.pop("vpai_filters", {}))
        countries = filters.pop("countries", None)
        if countries:
            vpai_filters["company_country_code"] = {"values": list(countries)}

        self._spend("fetch-entities-statistics")
        response = self._runner.run(
            "fetch-entities-statistics",
            args={"entity_type": entity_type, "filters": vpai_filters},
            tool_reasoning="Aggregate company statistics for the current discovery filters.",
        )
        self._record_actual_credits(response)
        return response

    def search_companies(self, **filters: Any) -> list[ProviderCompanyRecord]:
        vpai_filters = dict(filters.pop("vpai_filters", {}))
        countries = filters.pop("countries", None)
        if countries:
            vpai_filters["company_country_code"] = {"values": list(countries)}
        number_of_results = filters.pop("number_of_results", self._sample_gate_rows())

        self._spend("fetch-entities", number_of_results=number_of_results)
        response = self._runner.run(
            "fetch-entities",
            args={"entity_type": "businesses", "filters": vpai_filters},
            tool_reasoning="Find companies matching the current ICP discovery filters.",
            number_of_results=number_of_results,
        )
        self._record_actual_credits(response)
        return [self._row_to_company_record(row) for row in self._rows(response)]

    def enrich_company(self, domain: str) -> ProviderCompanyRecord | None:
        business_id = self._match_business_id(domain)
        if business_id is None:
            return None

        enrichments = ["firmographics"]
        self._spend("enrich-business", business_ids=[business_id], enrichments=enrichments)
        response = self._runner.run(
            "enrich-business",
            args={"business_ids": [business_id], "enrichments": enrichments},
            tool_reasoning=f"Enrich {domain} with firmographic data (size, revenue, industry).",
        )
        self._record_actual_credits(response)
        firmographics = self._enrich_business_fields(response)
        if not firmographics:
            return None
        # Real field names confirmed against a live call (module docstring):
        # name, country_name, number_of_employees_range, yearly_revenue_range,
        # naics_description — the same band-not-exact-figure shape as
        # fetch-entities. No `employee_count`/`revenue`/`industry` fields
        # exist in the real response; those are left unset here rather than
        # invented, same policy as _row_to_company_record.
        return ProviderCompanyRecord(
            company_name=firmographics.get("name") or domain,
            domain=domain,
            headquarters_country=normalize_country_to_iso_alpha2(firmographics.get("country_name")),
            employee_count=None,
            reported_revenue_usd=None,
            industry=firmographics.get("naics_description"),
            business_model=None,
            company_type=None,
            technologies=[],
            raw=firmographics,
        )

    def _event_description(self, data: dict[str, Any]) -> str:
        """CONFIRMED (real fetch-businesses-events call, module docstring):
        `data`'s shape varies by event type. Narrative events
        (new_product, new_partnership, ...) carry `snippet`/`title`/`link`.
        Structured events (hiring_in_*_department, increase_in_*, ...)
        carry none of those — only fielded data like `department`,
        `job_titles`, `job_count`, `location`. There is no single
        description field common to both, so: use `snippet` when present
        (narrative events), otherwise synthesize a compact description
        from whatever fields the structured event actually has."""
        if data.get("snippet"):
            snippet: str = data["snippet"]
            return snippet
        parts = [f"{k}={v}" for k, v in data.items() if k != "event_name" and v is not None]
        return "; ".join(parts)

    def get_company_events(self, domain: str) -> list[CompanyEventRecord]:
        business_id = self._match_business_id(domain)
        if business_id is None:
            return []

        self._spend("fetch-businesses-events", business_ids=[business_id])
        response = self._runner.run(
            "fetch-businesses-events",
            args={"business_ids": [business_id], "event_types": DEFAULT_BUSINESS_EVENT_TYPES},
            tool_reasoning=(
                f"Retrieve business events (funding, launches, partnerships) for {domain}."
            ),
        )
        self._record_actual_credits(response)
        # CONFIRMED shape (real call, module docstring): top-level
        # `output_events`, each `{event_name, event_time, event_id, data,
        # business_id}` — NOT the `sample_rows` envelope other operations
        # use. `_rows()` deliberately isn't reused here.
        events: list[CompanyEventRecord] = []
        for row in response.get("output_events") or []:
            data = row.get("data") or {}
            event_name = row.get("event_name", "unknown")
            events.append(
                CompanyEventRecord(
                    account_domain=domain,
                    event_type=event_name,
                    title=data.get("title") or event_name.replace("_", " ").title(),
                    description=self._event_description(data),
                    event_date=_parse_date(row.get("event_time")),
                    source_url=data.get("link"),
                    confidence=0.8,
                )
            )
        return events

    def find_contacts(
        self, domain: str, account_status: AccountStatus | None = None
    ) -> list[ContactRecord]:
        """Structural gate, not caller-dependent (spec §10): the first line
        of this method calls review/guardrails.py:require_contact_discovery_approved,
        which raises ContactDiscoveryNotApprovedError unless
        account_status == AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY.
        Omitting account_status entirely — matching the base
        CompanyDataProvider protocol's `find_contacts(self, domain)`
        signature exactly — is itself treated as unapproved and refused,
        rather than defaulting to permissive. There is no way to reach the
        real vpai call below without an approved status actually being
        passed in."""
        if account_status is None:
            raise ContactDiscoveryNotApprovedError(
                "find_contacts requires an approved account_status; none was provided "
                "(defaulting to unapproved, not permissive)."
            )
        require_contact_discovery_approved(account_status)

        business_id = self._match_business_id(domain)
        if business_id is None:
            return []

        # spec §6: "identify up to two relevant decision-makers"
        number_of_results = 2
        self._spend("fetch-entities", number_of_results=number_of_results)
        response = self._runner.run(
            "fetch-entities",
            args={
                "entity_type": "prospects",
                "filters": {"business_id": {"values": [business_id]}},
            },
            tool_reasoning=f"Identify up to two relevant decision-makers at {domain}.",
            number_of_results=number_of_results,
        )
        self._record_actual_credits(response)
        return [
            ContactRecord(
                account_domain=domain,
                name=row.get("full_name") or row.get("name", ""),
                exact_title=row.get("job_title") or row.get("title", ""),
                # CONFIRMED (real fetch-entities(prospects) call, module
                # docstring): the field is `linkedin` (a bare
                # "linkedin.com/in/..." string, no scheme) — NOT
                # `linkedin_profile`, which is fetch-entities(businesses)'
                # field name for the same concept on a different entity
                # type. Same lesson as before: nothing about one
                # entity_type's field names predicts another's.
                public_profile_url=_normalize_linkedin_url(row.get("linkedin")),
                role_change_date=None,
                # Prospect discovery never returns contact values (vpai
                # docs: "not email or phone values") — email stays unset
                # until a separate, separately-approved enrich_contact_email.
                email=None,
            )
            for row in self._rows(response)
        ]

    def _resolve_contact_types(self) -> list[str]:
        """Determines which contact fields to request from vpai. Reads
        `config/providers.yaml credit_budget.retrieve_phone_numbers`
        (default False) rather than hardcoding `["email"]` as a bare
        literal, so that whether phone is ever included is a real,
        executing decision — not just an absence of a phone branch.
        `guard_phone_retrieval_call()` is called here, for real, whenever
        that config flag is set — spec §23's hard denial fires from an
        actually-reached code path, not only from the literal contents of
        a hardcoded list. The hardcoded `["email"]` default below remains
        as a second, independent layer, per spec's defense-in-depth
        pattern elsewhere (see docs/vibe-credit-strategy.md 'Phone
        numbers')."""
        retrieve_phone = self._providers_config["credit_budget"].get(
            "retrieve_phone_numbers", False
        )
        if retrieve_phone:
            guard_phone_retrieval_call()  # always raises — phone stays unreachable
        return ["email"]

    def enrich_contact_email(
        self,
        contact: ContactRecord,
        account_status: AccountStatus | None = None,
        email_enrichment_approved: bool = False,
    ) -> ContactRecord:
        """Structural gate, not caller-dependent (spec §6/§11/§23: a
        second, separate approval beyond contact discovery). The first
        line calls review/guardrails.py:require_email_enrichment_approved,
        which itself requires
        account_status == AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY
        *and* email_enrichment_approved=True — omitting account_status
        entirely is treated as unapproved and refused, matching
        find_contacts. Phone retrieval is blocked by
        `_resolve_contact_types` actually calling
        review/guardrails.py:guard_phone_retrieval_call when config would
        otherwise allow it — see that method's docstring. There is no
        enrich_contact_phone method on this provider or the
        CompanyDataProvider protocol at all."""
        if account_status is None:
            raise EmailEnrichmentNotApprovedError(
                "enrich_contact_email requires an approved account_status; none was "
                "provided (defaulting to unapproved, not permissive)."
            )
        require_email_enrichment_approved(account_status, email_enrichment_approved)

        prospects_to_match = [{"full_name": contact.name, "company_name": contact.account_domain}]
        self._spend("match-prospects", prospects_to_match=prospects_to_match)
        match_response = self._runner.run(
            "match-prospects",
            args={"prospects_to_match": prospects_to_match},
            tool_reasoning=(
                f"Find the Explorium prospect ID for {contact.name} at {contact.account_domain}."
            ),
        )
        self._record_actual_credits(match_response)
        match_rows = self._rows(match_response)
        if not match_rows:
            return contact
        prospect_id = match_rows[0].get("prospect_id") or match_rows[0].get("id")
        if prospect_id is None:
            return contact
        prospect_id = str(prospect_id)

        contact_types = self._resolve_contact_types()
        self._spend(
            "enrich-prospects",
            prospect_ids=[prospect_id],
            enrichments=["contacts"],
            parameters={"contact_types": contact_types},
        )
        response = self._runner.run(
            "enrich-prospects",
            args={
                "prospect_ids": [prospect_id],
                "enrichments": ["contacts"],
                "parameters": {"contact_types": contact_types},
            },
            tool_reasoning=(
                f"Retrieve a business email address for {contact.name} (email only, no phone)."
            ),
        )
        self._record_actual_credits(response)
        contacts_result = self._enrichment_result(response, "contacts")
        email = contacts_result.get("email") if contacts_result else None
        if not email:
            emails = contacts_result.get("emails") if contacts_result else None
            email = emails[0] if emails else None
        if not email:
            return contact
        return contact.model_copy(update={"email": email})
