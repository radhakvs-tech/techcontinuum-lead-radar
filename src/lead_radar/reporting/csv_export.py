"""CSV report writers. Spec §15."""

from __future__ import annotations

import csv
from pathlib import Path

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
    """rows should already be filtered to accounts requiring a human decision
    (review_status == PENDING_HUMAN_REVIEW)."""
    write_qualified_accounts_csv(rows, path)
