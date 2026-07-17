# Human-review process

Spec §10. No account moves directly from automated discovery to contact
enrichment — a human decision is always in the loop before that boundary.

## Status machine (`models/enums.py:AccountStatus`)

```
DISCOVERED → PRELIMINARY_QUALIFIED → SCORED → PENDING_HUMAN_REVIEW
    → APPROVED_FOR_CONTACT_DISCOVERY → CONTACTED → POSITIVE_REPLY | NEGATIVE_REPLY
    → MEETING_BOOKED
  (or, at any point): → REJECTED | WATCHLIST
```

`discovery/pipeline.py:REVIEW_REQUIRED_CLASSIFICATIONS` determines which
score classifications route an account to `PENDING_HUMAN_REVIEW`
(`HIGH_INTENT`, `HIGH_PRIORITY_REVIEW`, `WATCHLIST`, `GOOD_FIT_LOW_SIGNAL`).
Weak-signal accounts stay at `SCORED` without entering the review queue.

## Reviewer labels (`models/enums.py:ReviewerLabel`)

`HIGH_PRIORITY`, `GOOD_FIT_LOW_SIGNAL`, `WRONG_ICP`, `WEAK_SIGNAL`,
`INSUFFICIENT_INFORMATION`, `DUPLICATE`, `NOT_SUITABLE_FOR_SMALL_ADVISORY`.

## Audit trail

Every decision is persisted as a `HumanReview` row
(`review/workflow.py:apply_review_decision`): reviewer, timestamp, old
status, new status, reviewer label, free-text reason, and the
`scoring_version` in effect at the time — so a decision remains
interpretable even after scoring weights change later.

## CLI

```bash
lead-radar review list
lead-radar review approve 123 --reason "Customer-facing AI launch plus simultaneous platform hiring"
lead-radar review reject 123 --reason "Wrong ICP: pure staffing agency"
```

## What Phase 1 does *not* do yet

`APPROVED_FOR_CONTACT_DISCOVERY` is a real status the CLI can set, but no
code currently reads it to fetch contacts — that logic doesn't exist until
Phase 4. What exists today is the guard that will gate it:
`review/guardrails.py:can_discover_contacts` / `can_enrich_email`, which
require the account status (and, for email, a second explicit approval)
before any future contact-fetching code is allowed to run. See
`docs/evidence-policy.md` for the related LinkedIn/employee-data
restrictions.
