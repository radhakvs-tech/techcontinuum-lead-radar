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

## Known limitations — public web research (Phase 3a)

Discovered through real (human-authorized) validation fetches against
`ManualUrlProvider`, not theorized in advance — see the session that added
`research/`, `providers/manual_url_provider.py`, and
`providers/pattern_guess_provider.py` for the specific pages involved.

- **No JavaScript execution.** The fetcher (`research/http_fetch.py`,
  shared by `ManualUrlProvider` and `PatternGuessProvider`) is `httpx`
  fetching raw HTML — it does not run a browser or execute client-side
  JS. Client-rendered marketing sites (Next.js/React and similar — an
  increasingly common stack among our actual SaaS ICP) will deliver a
  near-empty HTML shell with the real content populated after load, and
  the structural extractor (`research/evidence_extraction.py`) will
  correctly find nothing to extract. Confirmed live: Hasura's own
  `hasura.io/changelog` (a Next.js app) returned `200 OK` but zero
  `<p>`/`<li>` tags in the delivered HTML — only two server-rendered
  headings. This affects every provider equally, since they all share the
  same fetcher; it is not fixable by better URL-finding, only by adding a
  headless-browser-backed fetch path, which is out of scope for Phase 3a.

- **Page chrome can produce false-positive matches attributed to the
  wrong entity.** Confirmed live on `github.com/hasura/graphql-engine/
  releases`: GitHub's own navigation menu contains marketing copy
  ("Enterprise platform — AI-powered developer platform") that matched
  `generic_ai_marketing_only` and was extracted as Evidence — correctly
  downgraded to the weakest tier (`GENERAL_INDUSTRY_CONSIDERATION`,
  confidence 0.3) by the generic-marketing-phrase rule, but attributed to
  GitHub's chrome, not the researched company's actual content. The 95
  genuine release-note blocks on that same page (real version tags, real
  engineering text) extracted zero matches — correctly, since Hasura's
  infra/bugfix changelog language isn't in our AI/hiring/cost-focused
  taxonomy, not a false negative. The structural parser does not currently
  distinguish "this company's own content" from "boilerplate chrome of
  the hosting platform" (nav bars, footers, third-party widget text) —
  this matters most for pages hosted on a shared platform (GitHub, a
  hosted docs/blog CMS) rather than a company's own domain.

- **`PatternGuessProvider` will miss non-standard URL structures.** It
  only tries a small, fixed set of conventional paths per role
  (`config/url_patterns.yaml`: `/careers`, `/changelog`, etc.) — a company
  using an ATS-hosted careers page, a non-English path, or an unconventional
  URL scheme will resolve to nothing from pattern-guessing and needs a
  human-curated `ManualUrlProvider` manifest entry instead (which
  `PatternGuessProvider` falls back to automatically per role).

- **`PatternGuessProvider`'s company-name check is a heuristic, not
  proof.** It only checks whether the fetched page's `<title>`/meta
  description plausibly names the expected company (substring or
  token-overlap match) — confirmed necessary, not theoretical, by this
  session's own validation: `gozen.com/jobs` returned `200 OK` and looked
  like a plausible careers page, but is an entirely unrelated company that
  happens to share the "GoZen" name with `gozen.io`, the one this
  pipeline actually cares about. The check catches a wrong-company hit
  when the page's own title/description says so — it cannot verify a
  guessed page is *current* (e.g., a changelog page that exists but hasn't
  been updated in two years), and a company whose real name differs enough
  from its domain label (and has no `company_names` entry supplied) may
  fail the check even when the page is correct.

- **Not all "preferred sources" (spec §5) are equally reliable to
  fetch.** GitHub, press-release wire services, and ATS-hosted job boards
  (Greenhouse, Lever) tend to be server-rendered and stable; a company's
  own marketing site is increasingly likely to be a client-rendered SPA.
  Source-sequence priority (`research/source_sequence.py`) should lean
  toward the more reliable source when both exist for the same fact — e.g.
  prefer a Greenhouse-hosted job listing over the company's own `/careers`
  page if both are available, and GitHub release notes over a vendor's
  own in-app changelog widget.

## Later phases (interfaces exist, implementations do not)

- `VibeProvider` (Phase 2) — real Vibe Prospecting integration via the
  `vpai` CLI.
- `WebResearchProvider` implementations beyond the Protocol stub (Phase 3).
- `llm/` package wiring the Anthropic API into evidence classification and
  dossier drafting (Phase 3).
- Actual contact/email fetching behind `review/guardrails.py` (Phase 4).
- Outside-in snapshot generator, PostgreSQL guidance, review dashboard
  (Phase 5).
