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
inferred. Phase 3a's structural, keyword-based extraction
(`research/evidence_extraction.py`) now classifies free-text web evidence
across all four tiers using fixed rules (which phrase matched, which
`source_type` it came from, whether hedging language is present) — not
judgment. Genuine judgment-based classification (LLM-assisted, evidence
summarisation, pain-track detection) is still Phase 3b's job, and prompts
built for it must not infer `REASONABLE_INFERENCE` or worse from mere
absence of information.

## Evidence → Signal conversion: a binding constraint (not yet built)

No code path converts `Evidence` rows into `Signal` rows for research-
derived evidence yet — Phase 3a's structural extraction only ever writes
`Evidence`. Scoring (`scoring/engine.py:score_account`) reads exclusively
from `Signal`, so today this is moot: a `GENERAL_INDUSTRY_CONSIDERATION`
or `UNKNOWN_REQUIRING_VALIDATION` tier `Evidence` row currently has zero
effect on any score. It stops being moot the moment that bridge is built
(scoped under Phase 3 in `docs/future-roadmap.md`), so the rule is
recorded here first, before that code exists:

**`GENERAL_INDUSTRY_CONSIDERATION` and `UNKNOWN_REQUIRING_VALIDATION` tier
evidence must never convert into a `Signal` that counts toward the
`minimum_independent_signals` or `minimum_direct_commitment_signals`
requirements of the `HIGH_INTENT` evidence bar (spec §5,
`scoring/engine.py:_meets_high_intent_bar`).**

This must be an exclusion by classification tier, not by confidence
weighting — lowering `Evidence.confidence` for a weaker tier is not
sufficient protection. `scoring/engine.py:_intent_signal_contributions`
only filters on `contribution > 0`; a lower confidence still produces a
smaller *positive* contribution for any `signal_key` with positive weight,
so it does not exclude that signal from the independent-signal count or
the direct-commitment check.

Confirmed by direct proof, not just reasoning: `generic_ai_marketing_only`
(the one `signal_key` `GENERAL_INDUSTRY_CONSIDERATION` currently maps to)
happens to be self-protecting today only because `config/scoring.yaml`
gives it a *negative* weight (`-10`), so its contribution is always
negative and gets filtered out incidentally, not by design. A hedged
`UNKNOWN_REQUIRING_VALIDATION` match has no equivalent protection: e.g.
"we are exploring whether to launch an autonomous agent" still
structurally tags as `signal_type=action_taking_agent`, which carries a
*positive* weight (12) and is one of the configured
`direct_commitment_signals` (`config/signal_taxonomy.yaml`). Simulating a
naive `Signal(signal_key="action_taking_agent", confidence=0.35)`
conversion from two independent pages currently produces
`meets_high_intent_evidence_bar=True` — exactly the outcome spec §5
forbids: not based only on marketing phrases, and by the same logic, not
based on hedged/aspirational language read as a firm commitment either.

Whoever builds the Evidence→Signal bridge must gate on
`Evidence.classification` explicitly: only `OBSERVED_FACT` and
`REASONABLE_INFERENCE` tier evidence may ever produce a `Signal` that
participates in the independent-signal or direct-commitment checks.
`GENERAL_INDUSTRY_CONSIDERATION` and `UNKNOWN_REQUIRING_VALIDATION` tier
evidence may still be surfaced elsewhere (e.g. a dossier's "what remains
unknown" section) but must never move the `HIGH_INTENT` needle on its own.

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
