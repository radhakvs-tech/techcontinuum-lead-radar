# TechContinuum Lead Radar

Evidence-driven B2B lead discovery and ranking for TechContinuum, a two-person
senior advisory firm helping established SaaS companies move AI-enabled
products from experimentation to dependable production.

> **Status: Phase 2 (of 5)** — Phase 1 (scaffold, config, database, core
> models, mock/CSV providers, hard gates, deterministic scoring, tests, CLI)
> plus Phase 2's `VibeProvider` (real `vpai` CLI integration), cost
> estimation, multi-account credit-expiry priority logic, and retry/caching
> are done. See `docs/spec.md` §20 for the full phase plan and `claude.md`
> for phase-discipline rules. `VibeProvider`'s output parsing is only
> live-verified for `search_companies`/`company_statistics` — see
> `providers/vibe_provider.py`'s module docstring and
> `docs/vibe-credit-strategy.md` before trusting its other methods in
> production. Public web research, LLM-assisted classification, dossier
> generation, and contact/email enrichment approval workflows are **not yet
> implemented** — they arrive in Phases 3–4.

## Business purpose

TechContinuum helps established SaaS companies evolve from AI-assisted
features to reliable, governed and economically viable agentic products —
without cloud costs, platform complexity or legacy constraints spiralling out
of control. Lead Radar discovers, researches, qualifies and ranks companies
likely to need that kind of external advisory, using deterministic,
explainable scoring rather than LLM-invented scores. It is explicitly **not**
a mass-emailing system: it never sends email and never scrapes personal
LinkedIn profiles.

## Architecture (current)

```
config/            YAML configuration: ICP, scoring weights, signal & title
                    taxonomies, exclusions, provider settings
src/lead_radar/
  settings.py       Pydantic settings loader (env + YAML)
  db.py             SQLite engine/session setup (SQLModel)
  models/           Core entities (Account, Evidence, Signal, ScoreRun, ...)
  providers/        CompanyDataProvider protocol + MockProvider + CsvProvider
  discovery/        ICP hard-gate filtering
  scoring/          Deterministic, explainable scoring engine
  review/           Human-review status machine + contact/email guardrails
  reporting/        CSV/JSONL/Markdown report generation
  cli.py            Typer CLI entry point
tests/              pytest suite (hard gates, scoring, recency decay,
                    dedup, evidence requirements, credit limits, guardrails)
scripts/
  seed_demo_data.py Seeds synthetic demo companies and runs the pipeline
```

Everything runs against a local SQLite database. There is no distributed
architecture and no background services — this is a single-user, CLI-first
application by design.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12 (uv will fetch it
automatically).

```bash
make setup       # uv sync --group dev
cp .env.example .env
```

## Environment variables

See `.env.example`. None are required to run Phase 1 — the mock provider
needs no credentials. `ANTHROPIC_API_KEY` and `VPAI_API_KEY` are reserved for
later phases.

## Vibe Prospecting integration

`providers/base.py` defines the `CompanyDataProvider` protocol described in
spec §6; `MockProvider`, `CsvProvider`, and now `VibeProvider` all implement
it. `VibeProvider` (`providers/vibe_provider.py`) shells out to the real
`vpai` CLI (via `providers/vpai_runner.py`, with retry + per-run caching)
after inspecting `vpai`'s live tool schemas, per spec §6. Every real call is
gated by `providers/vibe_cost_heuristic.py` (published Explorium credit
rates — not vendor-API-confirmed, since `vpai` has no cost API) and
`providers/credit_control.py` (`credit_budget.maximum_per_run` defaults to
0, so nothing spends until a human explicitly raises it). Multi-account
priority (`providers/vibe_accounts.py`) ranks by soonest credit expiry, not
balance — see `docs/vibe-credit-strategy.md` for the full model, including
which of `VibeProvider`'s response-parsing paths are live-verified versus
inferred from documentation only.

## CSV import format

`lead-radar import-vibe-csv <path>` expects one row per company with at
least: `company_name, domain, headquarters_country, employee_count,
reported_revenue, industry, business_model, company_type, technologies`.
Extra columns are ignored. Rows are deduplicated by canonical domain and
imports are idempotent — re-importing the same file updates existing
accounts rather than duplicating them.

## CLI examples

```bash
lead-radar init-db
lead-radar import-vibe-csv data/imports/vibe-companies.csv
lead-radar discover --countries US,GB,DE,AU,SG --dry-run
lead-radar score --account-id 1
lead-radar run --countries US,GB,DE,AU,SG --dry-run
lead-radar export --minimum-score 65 --format csv
lead-radar review list
```

## Scoring explanation

Scores are computed entirely by deterministic Python (`scoring/`), never by
an LLM. Each account is scored 0–100 across six weighted dimensions (ICP
fit, AI-transition pressure, cloud/modernisation pain, martech agentisation
pressure, external-advisor likelihood, evidence quality/recency). Individual
signal weights decay over time using a half-life recency function and are
scaled by confidence. See `docs/scoring-model.md` for the full model and
`config/scoring.yaml` for the live weights. A company cannot be classified
`HIGH_INTENT` on numeric score alone — it must also satisfy the minimum
evidence-independence and recency rules in `docs/evidence-policy.md`.

## Evidence standards

Every material claim is stored with source URL, title, type, published/
observed dates, a confidence level, and an independence group so that
duplicate or copied sources cannot be double-counted. See
`docs/evidence-policy.md`.

## Credit-control model

Vibe credit budgeting (`credit_budget` in `config/providers.yaml`) is
defined now so tests can enforce it, even though the real Vibe connector
ships in Phase 2. Budgets default to zero and must be explicitly raised;
dry-run cost estimates are required before any costly operation. See
`docs/vibe-credit-strategy.md`.

## Privacy and compliance guardrails

- No emails are ever sent; there is no outreach/sequencing feature.
- No personal LinkedIn profiles are scraped.
- No phone numbers are retrieved (`retrieve_phone_numbers` is hard-disabled).
- Contact discovery cannot run until an account has passed human approval;
  email enrichment requires a second, separate approval. See
  `src/lead_radar/review/guardrails.py` and `docs/human-review.md`.

## Human-review process

See `docs/human-review.md` for the full status machine
(`DISCOVERED` → ... → `APPROVED_FOR_CONTACT_DISCOVERY` / `REJECTED` /
`WATCHLIST`) and reviewer labels. `lead-radar review list` and
`lead-radar review approve` operate on this workflow.

## How to add a new signal

Add an entry under `signals:` in `config/scoring.yaml` with a `weight` and
`half_life_days`, then reference the same key from wherever evidence is
classified into that signal type. No code changes are required for weight
tuning.

## How to change ICP criteria

Edit `config/icp.yaml` (geography, employee band, revenue band, included/
excluded company types). Hard gates in `discovery/hard_gates.py` read this
file at run time.

## How to add a new data provider

Implement the `CompanyDataProvider` protocol in `providers/base.py` (see
`providers/mock.py` for the simplest example) and register it in
`config/providers.yaml`.

## How to run tests

```bash
make lint
make typecheck
make test
make demo
```

## Known limitations (Phase 1)

- No real Vibe Prospecting connector yet — only Mock and CSV providers.
- No public web research, no LLM-assisted evidence classification, no
  dossier generation yet (Phase 3).
- No actual contact/email enrichment yet — only the approval guardrails
  that will gate it (Phase 4).
- Offer recommendation matching (spec §9) is not yet wired into the CLI.
