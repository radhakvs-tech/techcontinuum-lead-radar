# Scoring model

All scoring is deterministic Python (`src/lead_radar/scoring/`), driven by
`config/scoring.yaml`. An LLM never computes or adjusts the final number
(spec §8, §23) — in Phase 1 there is no LLM in the loop at all.

## Dimensions (100 points total)

| Dimension | Points | Computed from |
|---|---|---|
| ICP and commercial fit | 20 | `_icp_fit_score`: revenue-band fit + company-type fit |
| AI/product-transition pressure | 20 | Signals tagged `dimension: ai_transition_pressure` |
| Cloud, platform and modernisation pain | 20 | Signals tagged `dimension: cloud_modernisation_pain` |
| Martech agentisation pressure | 10 (0 for non-martech) | Signals tagged `dimension: martech_agentisation_pressure` |
| External-advisor likelihood | 15 | Signals tagged `dimension: external_advisor_likelihood` |
| Evidence quality and recency | 15 | `_evidence_quality_score`: independence, recency, avg. confidence |

## Non-martech reallocation

For accounts whose `company_type` is not in
`scoring/engine.py:MARTECH_COMPANY_TYPES`, the 10 martech points are
redistributed proportionally across `ai_transition_pressure`,
`cloud_modernisation_pain`, and `external_advisor_likelihood` (weighted by
their existing point allocations), per `non_martech_reallocation_targets`
in `config/scoring.yaml`. See `dimension_max_points()`.

## Recency decay

```
effective_weight = base_weight * confidence * (0.5 ** (age_days / half_life_days))
```

A signal with no known date is treated conservatively (`scoring/recency.py`):
age is assumed to be `3 * half_life_days` and confidence is halved, rather
than assumed to have happened today.

## Classification

```
classification:
  high_intent: 80
  high_priority_review: 65
  watchlist: 45
```

`HIGH_INTENT` additionally requires (`high_intent_requirements` in
`config/scoring.yaml`, spec §5 evidence quality rules):

- at least 2 signals from *independent* sources (same `independence_group`
  — e.g. the same press release syndicated twice — counts once),
- at least 1 signal classified as a direct product/engineering/business
  commitment (`direct_commitment_signals` in `config/signal_taxonomy.yaml`),
- at least 1 material signal within the last 90 days.

An account meeting the 80-point threshold but failing this bar is
downgraded to `HIGH_PRIORITY_REVIEW` rather than `HIGH_INTENT` — the raw
score alone never grants the label (spec §8).

Below the `watchlist` threshold, accounts split into `GOOD_FIT_LOW_SIGNAL`
(good ICP fit, no positive material signal), `INSUFFICIENT_INFORMATION`
(poor fit and no signal), or `IGNORE_WEAK_SIGNAL` (some signal, but too
weak). `IGNORE_WRONG_ICP` is assigned by the hard-gate stage before scoring
even runs, not by the scoring engine.

## Explainability

Every `ScoreContribution` row records: signal key, dimension, evidence
source, original weight, recency-adjusted weight, confidence, signed
contribution, a human-readable reason, and any cap applied (e.g. "martech
dimension reallocated for non-martech account"). `lead-radar score
--account-id N` prints this breakdown.

## Recommended offer matching

`scoring/offers.py` picks among TechContinuum's four offers based on which
scored pain dimension is strongest, with a light heuristic to distinguish
cloud-economics pressure from a modernisation programme. This is a
first-pass heuristic, not implemented in Phase 1's CLI as its own command —
richer offer matching using web-research evidence is future work.

## Changing weights

Edit `config/scoring.yaml` — no code changes needed. `scoring_version` in
that file should be bumped whenever weights change materially, since it is
persisted on every `ScoreRun` for reproducibility.
