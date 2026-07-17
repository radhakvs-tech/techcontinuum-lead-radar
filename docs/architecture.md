# Architecture

## Status

Reflects Phase 1 only (see `docs/spec.md` §20 and `claude.md` for phase
discipline). Boxes marked *(later phase)* below are interfaces that exist
today but have no working implementation yet.

## Component diagram

```
                         ┌─────────────────────┐
                         │        CLI           │
                         │  (Typer, cli.py)      │
                         └──────────┬────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                      │
     ┌────────▼────────┐  ┌─────────▼─────────┐  ┌─────────▼─────────┐
     │  discovery/       │  │   scoring/         │  │  reporting/        │
     │  hard_gates       │  │   engine, recency,  │  │  csv_export,       │
     │  ingest (dedup)   │  │   offers, models    │  │  evidence_export,  │
     │  evidence_pipeline│  │   (deterministic,    │  │  run_summary       │
     │  pipeline          │  │    no LLM — §8/§23)  │  │                    │
     └────────┬───────────┘  └─────────┬───────────┘  └─────────┬──────────┘
              │                        │                         │
     ┌────────▼────────┐     ┌─────────▼─────────┐     ┌─────────▼─────────┐
     │  providers/        │   │      db.py          │   │  templates/         │
     │  base (Protocol)   │   │  SQLModel + SQLite   │   │  Jinja2 (.md.j2)    │
     │  mock, csv          │   │                      │   │                      │
     │  vibe (later phase) │   └──────────────────────┘   └──────────────────────┘
     │  web (later phase)  │
     └──────────────────────┘

     review/                  llm/ (later phase)
     guardrails, workflow     Anthropic-backed evidence
     (human-review status     classification — application
     machine + contact/email  works without it (§17)
     approval gates)
```

## Data flow (Phase 1)

1. **Discover**: a `CompanyDataProvider` (`MockProvider` or `CsvProvider`)
   returns `ProviderCompanyRecord`s.
2. **Hard gates**: `discovery/hard_gates.py` applies geography, employee-band,
   and company-type rules from `config/icp.yaml`. Missing revenue/ARR is
   flagged, never rejected.
3. **Ingest**: `discovery/ingest.py` upserts an `Account` by canonical
   domain (idempotent) and records any data-quality conflicts.
4. **Signal enrichment**: `discovery/evidence_pipeline.py` turns provider
   `CompanyEventRecord`s into `Evidence` + `Signal` rows. In Phase 1 there is
   no LLM, so provider events map directly to signal keys — free-text
   classification is a later-phase concern once a `WebResearchProvider`
   exists.
5. **Score**: `scoring/engine.py` computes a deterministic 0–100 score
   across six weighted dimensions with recency decay, persists a
   `ScoreRun` + `ScoreContribution` rows, and classifies the account.
6. **Report**: `reporting/` writes `qualified_accounts.csv`,
   `review_queue.csv`, `evidence.jsonl`, and `run_summary.md`.

## Why not more layers yet

Spec §22 explicitly asks for a single-user, CLI-first application — no
distributed architecture, no background workers, no web server. SQLite is
sufficient for the MVP; a PostgreSQL migration path is deferred to Phase 5.

## Later phases (interfaces exist, implementations do not)

- `VibeProvider` (Phase 2) — real Vibe Prospecting integration via the
  `vpai` CLI.
- `WebResearchProvider` implementations beyond the Protocol stub (Phase 3).
- `llm/` package wiring the Anthropic API into evidence classification and
  dossier drafting (Phase 3).
- Actual contact/email fetching behind `review/guardrails.py` (Phase 4).
- Outside-in snapshot generator, PostgreSQL guidance, review dashboard
  (Phase 5).
