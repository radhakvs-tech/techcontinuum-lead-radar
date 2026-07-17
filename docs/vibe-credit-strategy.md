# Vibe credit strategy

Spec §6. **Status: `VibeProvider` implemented** (`providers/vibe_provider.py`,
`providers/vpai_runner.py`, `providers/vibe_accounts.py`), built on top of
the credit-control model this document describes
(`config/providers.yaml`, `providers/credit_control.py`,
`providers/vibe_cost_heuristic.py`) — that model existed first so it
couldn't be bolted on as an afterthought.

**Real-call verification status:** only `fetch-entities` with
`entity_type: businesses` has ever been called for real (one 5-row Sample
Gate call, this session). `VibeProvider.search_companies` and
`company_statistics` are therefore parsed against a confirmed response
shape. Every other method (`enrich_company`, `get_company_events`,
`find_contacts`, `enrich_contact_email`) chains through `match-business`,
`enrich-business`, `fetch-businesses-events`, `fetch-entities`
(`entity_type: prospects`), `match-prospects`, or `enrich-prospects` —
none of which has been called live. Their response parsing rests on
inferences documented in detail in `providers/vibe_provider.py`'s module
docstring (shared "Session Storage" envelope assumption, plus the one
piece that *is* directly documented by vpai: `enrichment_results` as
per-key JSON strings). Do not treat those methods' output as reliable in
production before running each one, once, as its own small
explicitly-approved sample call.

## What vpai actually reports (investigated, not assumed)

Spec §6 asks the system to "estimate cost where supported." Before writing
any estimation code, `vpai` (v0.1.105, installed and authenticated via
`vpai login`) was checked directly for a balance/usage/cost API:

- `vpai whoami` — returns only auth status: `authenticated`, `auth_source`,
  `api_key_hint`, config/oauth file paths, token expiry. No credit, balance,
  or usage field of any kind.
- Every subcommand's `--help` and `--all-parameters` (the full MCP
  `inputSchema` JSON) was read in full. No command named
  `account`/`usage`/`balance`/`billing` exists, and no field anywhere —
  across `login`, `logout`, `whoami`, `config`, `match-business`,
  `match-prospects`, `fetch-entities`, `fetch-entities-statistics`,
  `fetch-businesses-events`, `fetch-prospects-events`, `enrich-business`,
  `enrich-prospects`, `autocomplete` — mentions credit, balance, usage,
  quota, or billing.
- The **one real, vendor-provided bounded-cost control** found:
  `fetch-entities --number-of-results` is documented as "total rows to
  collect across pages (default: 50). **Sample gate: 5.**" That 5-row cap
  is the actual dry run the vendor gives us — nothing else in the CLI
  offers a pre-flight cost check. (The same `--number-of-results` flag text
  appears in every subcommand's `--help` because the CLI shares one
  argument-parser template, but the description scopes its effect to
  `fetch-entities` specifically — no other command documents its own
  sample/dry-run gate.)
- To rule out a cost field only appearing at runtime (not in the static
  schema), one real live call was made:
  `vpai fetch-entities --args '{"entity_type":"businesses","filters":{"company_country_code":{"values":["US"]}}}' --number-of-results 5`.
  The full raw response was inspected field by field. Top level:
  `csv_path`, `session_id`, `row_count`, `request_count`, `total_results`,
  `columns`, `sample_rows`. Each row: `business_id`, `name`, `domain`,
  `logo`, `country_name`, `city_name`, `number_of_employees_range`,
  `yearly_revenue_range`, `website`, `business_description`, `region`,
  `naics`, `naics_description`, `sic_code`, `sic_code_description`,
  `business_intent_topics`, `events`, `linkedin_profile`. No cost, credit,
  or balance field anywhere.

**Conclusion: there is no vendor cost-estimate API to call.**
`estimate_query_cost` therefore cannot be a thin wrapper around a real vpai
endpoint the way `search_companies` etc. eventually will be. It is
implemented instead as a **local heuristic built on Explorium's published
credit rates** (`providers/vibe_cost_heuristic.py`,
`config/providers.yaml` `vibe_cost_heuristic.credit_rates`) rather than a
flat made-up multiplier — see "Published credit rates" below. Every
`CostEstimate` it returns still says plainly in `notes` which parts are a
published number vs. our own extrapolation, and that none of it is
vendor-API-confirmed. The real, bounded-cost check before any full-size
fetch remains vpai's own `--number-of-results 5` Sample Gate, not this
heuristic — `sample_gate_rows: 5` in config exists so callers are pointed
at it rather than trusting the estimate.

This is a real, load-bearing gap for the credit-budget model below: without
a vendor cost API, `check_budget` can only ever be as accurate as this
heuristic's published-rate-based guess. Phase 2's `VibeProvider` should
treat every non-free operation as "run the 5-row sample gate first, inspect
the actual result, then decide" rather than trusting the heuristic's number
to gate a large spend on its own.

## Published credit rates

`config/providers.yaml` `vibe_cost_heuristic.credit_rates` — sourced from
explorium.ai/pricing, the explorium.ai blog, and third-party comparison
reviews (supplied 2026-07-17). These are **real published figures**, a step
up from an arbitrary flat guess, but they are still **not confirmed via any
vpai API** (none exists — see above) and should be re-validated against an
actual invoice or credit ledger once one is available.

| Category | Rate | Applies to | Status |
|---|---|---|---|
| Generate/search/list/event actions | 1 credit | `fetch-entities`, `match-business`, `match-prospects`, `fetch-entities-statistics`, `fetch-businesses-events`, `fetch-prospects-events`, `autocomplete` | Published. **Interpreted as flat per call**, not per row — the published phrasing doesn't specify which, and this is our reading, not a vendor confirmation. |
| Enrichment | 1-5 credits, "depending on data type" | `enrich-business` (any type); `enrich-prospects` "profiles" | Published as a range with no per-type breakdown. We use the conservative upper bound (5) per record x enrichment-type pair for budgeting. |
| Fully enriched contact (prospect + email + phone) | 8 credits/prospect | `enrich-prospects` with `enrichments: ["contacts"]`, `contact_types` omitted or `["email","phone"]` | Published. |
| Phone-specific lookup | ~10 credits/prospect | `enrich-prospects`, `contact_types: ["phone"]` | Published (approximate). Notably *more* than the bundled full-contact rate — that's the vendor's own published pricing, not an inconsistency we introduced. |
| Email-only lookup | not published — using 5 credits/prospect as a stand-in | `enrich-prospects`, `contact_types: ["email"]` | **Not published.** Explorium only states email is "cheaper [than phone], same shared pool," with no exact figure. We reuse the conservative enrichment upper bound, which is at least consistent with "cheaper than 8 and 10." Flagged explicitly as our extrapolation in every estimate's `notes`. |

`fetch-entities`, `match-business`, and `match-prospects` also have
documented per-call row caps (50, 50, 40 respectively) carried in
`known_row_limits` — informational under the flat-per-call reading above,
but useful context in the estimate's `notes`.

## Budget defaults to zero

```yaml
credit_budget:
  maximum_per_run: 0
  maximum_per_week: 0
  require_cost_estimate: true
  retrieve_contacts_only_after_approval: true
  retrieve_email_only_after_approval: true
  retrieve_phone_numbers: false
```

`providers/credit_control.py:check_budget` refuses any operation whose
estimated cost would push spend past `maximum_per_run` — including when the
budget is the zero default. Raising the limit is an explicit, auditable
config change, not something a provider call can talk its way past.

## Credit expiry (round-robin must account for this, not just balance)

Free-trial credits expire **90 days** after grant; paid credits expire
**12 months** after purchase. **Neither type rolls over.** This matters
directly for the 4-6 account round-robin: a priority function that only
looks at *remaining balance* will happily let a large balance on an
account whose credits expire in 3 days sit unused while draining an
account with a smaller balance but months of runway left — burning the
near-expiry credits for nothing.

**Implemented**: `providers/vibe_accounts.py`'s `select_next_account` ranks
by **soonest expiry first**, not balance first: it picks whichever
non-expired, non-exhausted account's credits lapse soonest, treating
accounts with unrecorded `credits_granted_at` as expiring immediately
(conservative — spend down unrecorded-expiry credits rather than risk
letting them lapse unnoticed). Ties break on account identifier for
determinism. This requires a per-account `credits_expire_at`, which —
since `vpai` exposes no balance/usage API at all (see above) — comes from
account records the user maintains manually (e.g. signup date + 90 days
for trial accounts, purchase date + 12 months for paid), not from
anything queryable through the CLI. `VibeAccount.credits_granted_at`
is `None` by default, since only one account is authenticated today; set
it per account as more are added to `VIBE_ACCOUNT_EMAILS`.

## Flow (`VibeProvider`, `providers/vibe_provider.py`)

1. Prioritise the user's 4-6 authenticated Vibe accounts' free-credit
   limits before spending anything paid — round-robin across
   `VIBE_ACCOUNT_EMAILS` (`.env`), **ordered by soonest credit expiry, not
   remaining balance** (see "Credit expiry" above). Implemented via
   `VibeProvider.active_account`, though nothing yet switches vpai's live
   OAuth session per account — see that property's docstring.
2. Every real call goes through `VibeProvider._spend`, which calls
   `estimate_query_cost` — backed by `providers/vibe_cost_heuristic.py`'s
   published-rate heuristic, since no vendor cost API exists (see above) —
   before the real call, clearly labelled as unverified/published-not-API-
   confirmed. **Not yet wired**: persisting that estimate to the
   `ProviderUsage` table is still pipeline-layer work — `VibeProvider`
   exposes an in-memory `usage_log` list for now, not a DB write.
3. Refuse the operation if the projected spend would exceed the configured
   budget; surface a clear prompt asking the user how to proceed, including
   an estimated weekly cost (itself heuristic-derived, and presented as
   such).
4. Before any full-size, non-free `fetch-entities` call, run it with
   `--number-of-results 5` (the vendor's real Sample Gate) first and show
   the user that actual result — this is the genuine bounded-cost dry run,
   not step 4 below.
5. Print a dry-run summary (heuristic estimate + sample-gate result where
   applicable) before any costly export.
6. Require an explicit CLI flag for costly (non-free) operations.

## Account-first workflow (spec §6)

```
query statistics → fetch businesses → hard gates → low-cost signal
enrichment → score → public-source verification (promising accounts only)
→ human approval → identify ≤2 contacts → optional email enrichment
```

The pipeline never fetches people before their company has passed hard
gates and scoring — see `discovery/pipeline.py:run_discovery_pipeline`,
which only calls `get_company_events` for gate-passed accounts, and never
calls `find_contacts`/`enrich_contact_email` at all (that requires human
approval — Phase 4).

## Phone numbers

`retrieve_phone_numbers` is `false` by default in config, but this is
defense-in-depth only — the real guarantee is
`review/guardrails.py:guard_phone_retrieval_call`, a function that always
raises `PhoneRetrievalDisabledError`. Phone retrieval is not a
configurable option; there is no code path that can turn it on.
