# Future roadmap

Per `docs/spec.md` §20. Phase 1 is complete (repository scaffold,
configuration, database, core models, mock/CSV providers, hard gates,
deterministic scoring, tests, CLI, sample outputs — all passing `make
lint`, `make typecheck`, `make test`, `make demo`). Phase 2 has not started
(`claude.md`: work strictly one phase at a time).

## Phase 2 — Vibe Prospecting integration

- Inspect the live `vpai` CLI tool schemas before first use of each tool —
  do not assume parameters from this spec.
- Implement `VibeProvider` against `providers/base.py:CompanyDataProvider`.
- Wire real cost estimation and `ProviderUsage` credit tracking through
  `providers/credit_control.py`.
- Company-event enrichment via Vibe's business/event data.
- Retry and fetch-cache behaviour (idempotent — must not duplicate records
  on retry, per spec §18.17).

## Phase 3 — Public research and evidence generation

- `WebResearchProvider` implementations beyond the `ManualUrlProvider` /
  `MockWebProvider` stubs: per-domain fetch cache, robots/rate-limit
  respect, page-size and page-count limits.
- Free-text evidence extraction feeding the same `Evidence`/`Signal` tables
  Phase 1 already populates from structured provider events.
- LLM-assisted classification (`llm/` package, Anthropic API) — evidence
  summarisation, pain-track detection, validation-question drafting. The
  LLM never computes the final score (spec §8, §23) and the app must keep
  working with `llm.enabled: false`.
- `account_dossiers/<domain>.md` generation via `templates/account_dossier.md.j2`.

## Phase 4 — Approved contact discovery

- Real `find_contacts` / `enrich_contact_email` implementations behind the
  guards already defined in `review/guardrails.py`.
- Feedback import (`lead-radar feedback import`).

## Phase 5 — Optional extras

- `lead-radar snapshot --account-id` outside-in snapshot generator, with
  explicit observed/inferred/unknown/general-consideration separation and
  the required "not an internal audit" disclaimer (spec §16).
- PostgreSQL migration guidance (SQLite remains sufficient for the
  single-user CLI MVP).
- Optional lightweight review dashboard.
- Scheduling documentation for recurring runs.

## Known Phase 1 limitations

- Offer matching (`scoring/offers.py`) uses a simple strongest-dimension
  heuristic; it is not wired into a CLI command's report yet and will
  benefit from richer web-research evidence in Phase 3.
- `ResearchRun`, `Contact`, and email-verification fields exist as schema
  (spec §12) but are not populated by any running code path yet.
