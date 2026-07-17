# Evidence policy

Spec §5. Every material claim about an account must be traceable to
evidence — no conclusion is asserted "because an LLM said so" or "because
nothing was found."

## Required fields (`models/evidence.py:Evidence`)

`source_url`, `source_title`, `source_type`, `published_date`,
`observed_date`, `evidence_text`, `evidence_summary`, `signal_type`,
`confidence`, `independence_group`, `classification`.

## Classification

```
OBSERVED_FACT
REASONABLE_INFERENCE
GENERAL_INDUSTRY_CONSIDERATION
UNKNOWN_REQUIRING_VALIDATION
```

In Phase 1, evidence comes from structured provider events (mock/CSV data),
which are inherently `OBSERVED_FACT` — they were provider-labelled, not
inferred. Once a `WebResearchProvider` and LLM-assisted classification
exist (Phase 3), free-text evidence will be classified across all four
categories, and prompts must not infer `REASONABLE_INFERENCE` or worse from
mere absence of information.

## Independence grouping

Two pieces of evidence sharing the exact same `source_url` are the same
corroborating source and are grouped under one `independence_group`
(`discovery/evidence_pipeline.py:_independence_group`, a hash of the URL).
This prevents a single press release, syndicated across two mentions, from
being counted as two independent signals toward the `HIGH_INTENT` bar.

## Preferred sources

Company website, product/documentation pages, changelog, careers pages and
job descriptions, engineering blog, public GitHub presence, trust/security
pages, press releases, funding announcements, public conference talks,
company-authored social posts, and Vibe Prospecting business/event data.

## LinkedIn restrictions (hard constraint, spec §5, §23)

- No automated scraping of personal LinkedIn profiles.
- Never store or publish: personal photos, personal biographies, detailed
  career histories, personally-scraped contact details, or bulk employee
  skill lists.
- Company-authored LinkedIn posts may only be used via a permitted provider
  or a manually supplied URL.
- Employee-level information is only collected after an account passes
  human approval (spec §11), and only to identify up to two decision-makers
  — enforced by `review/guardrails.py` (Phase 1 defines the guard; actual
  fetching is Phase 4).

## Missing data

Missing dates reduce confidence and are treated conservatively in recency
decay (`scoring/recency.py`), never assumed to mean "today." Missing
revenue/ARR is recorded as a data-quality flag, never asserted as absence
of a capability ("no evaluation framework") — see `hard_gates.py` and the
`Account.data_quality_flags` field. Conflicting data (e.g. reported revenue
that contradicts an estimated range) is retained in full, with a flag
noting the conflict — never silently discarded (spec §23).
