"""CSV report writers. Spec §15."""

from __future__ import annotations

import csv
from pathlib import Path

from lead_radar.discovery.ingest import HARD_GATE_MISMATCH_FLAG_PREFIX
from lead_radar.models.enums import AccountStatus
from lead_radar.reporting.types import QualifiedAccountRow

QUALIFIED_ACCOUNTS_FIELDS = list(QualifiedAccountRow.model_fields.keys())


def write_qualified_accounts_csv(rows: list[QualifiedAccountRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ranked = sorted(rows, key=lambda r: r.total_score, reverse=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=QUALIFIED_ACCOUNTS_FIELDS)
        writer.writeheader()
        for row in ranked:
            writer.writerow(row.model_dump())


def write_review_queue_csv(rows: list[QualifiedAccountRow], path: Path) -> None:
    """Filters to accounts needing a (re-)review decision: those still
    PENDING_HUMAN_REVIEW, or those a human already decided on where fresh
    ingested data now conflicts with that decision — a
    `HARD_GATE_MISMATCH_FLAG_PREFIX`-prefixed flag surfaced in `unknowns`
    by discovery/ingest.py:ingest_company_record — and should be looked at
    again even though their status is e.g. APPROVED_FOR_CONTACT_DISCOVERY,
    not PENDING_HUMAN_REVIEW.

    Filtering lives here, not in each caller, because two callers
    (cli.py's `run` command and scripts/seed_demo_data.py) previously
    duplicated this exact condition independently — a single source of
    truth avoids them drifting apart again."""
    review_rows = [
        row
        for row in rows
        if row.review_status == AccountStatus.PENDING_HUMAN_REVIEW.value
        or HARD_GATE_MISMATCH_FLAG_PREFIX in row.unknowns
    ]
    write_qualified_accounts_csv(review_rows, path)
