# Vibe credit strategy

Spec §6. **Status: not yet integrated.** `VibeProvider` is a Phase 2 item —
this document describes the credit-control model that already exists
(`config/providers.yaml`, `providers/credit_control.py`) so it's in place
before any credit-consuming code is written, not bolted on afterward.

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

## Planned flow (Phase 2, once `vpai` is wired up)

1. Prioritise the user's 4-6 authenticated Vibe accounts' free-credit
   limits before spending anything paid — round-robin across
   `VIBE_ACCOUNT_EMAILS` (`.env`).
2. Once free limits are exhausted, call `estimate_query_cost` and record
   the estimate via `ProviderUsage` before the real call.
3. Refuse the operation if the projected spend would exceed the configured
   budget; surface a clear prompt asking the user how to proceed, including
   an estimated weekly cost.
4. Print a dry-run summary before any costly export.
5. Require an explicit CLI flag for costly (non-free) operations.

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
