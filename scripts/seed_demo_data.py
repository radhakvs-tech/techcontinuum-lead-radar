#!/usr/bin/env python3
"""Runs the full Phase 1 pipeline against MockProvider's synthetic demo
companies (spec §19) and writes sample outputs to data/exports/.

This is what `make demo` invokes. It deliberately resets the demo SQLite
database on every run so the output is reproducible from a clean slate
rather than accumulating duplicate evidence across repeated runs.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from lead_radar.db import get_session, init_db  # noqa: E402
from lead_radar.discovery import run_discovery_pipeline  # noqa: E402
from lead_radar.providers import MockProvider  # noqa: E402
from lead_radar.reporting import (  # noqa: E402
    RunSummary,
    build_qualified_account_row,
    write_evidence_jsonl,
    write_qualified_accounts_csv,
    write_review_queue_csv,
    write_run_summary,
)
from lead_radar.settings import get_icp_config  # noqa: E402

console = Console()

DB_PATH = REPO_ROOT / "data" / "lead_radar.db"
EXPORTS_DIR = REPO_ROOT / "data" / "exports"


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    console.print(f"[bold]Resetting demo database at {DB_PATH}[/bold]")
    init_db(DB_PATH)

    countries = get_icp_config()["geography"]["allowed_countries"]
    provider = MockProvider()

    with get_session(DB_PATH) as session:
        result = run_discovery_pipeline(session, provider, countries=countries)

        rows = [
            build_qualified_account_row(
                r.account, r.score_run, r.contributions, r.primary_pain_track, r.recommended_offer
            )
            for r in result.accounts_scored
        ]
        write_qualified_accounts_csv(rows, EXPORTS_DIR / "qualified_accounts.csv")

        review_rows = [r for r in rows if r.review_status == "PENDING_HUMAN_REVIEW"]
        write_review_queue_csv(review_rows, EXPORTS_DIR / "review_queue.csv")

        write_evidence_jsonl(result.evidence_rows, EXPORTS_DIR / "evidence.jsonl")

        signal_counter: Counter[str] = Counter()
        pain_track_counter: Counter[str] = Counter()
        for r in result.accounts_scored:
            pain_track_counter[r.primary_pain_track] += 1
            for c in r.contributions:
                if c.contribution != 0:
                    signal_counter[c.signal_key] += 1
        classification_counter = Counter(
            r.score_run.classification.value for r in result.accounts_scored
        )

        research_gaps = [
            f"{r.account.domain}: no configured weight for signal(s) "
            + ", ".join(
                sorted(
                    {
                        c.signal_key
                        for c in r.contributions
                        if c.cap_applied and "unconfigured" in c.cap_applied
                    }
                )
            )
            for r in result.accounts_scored
            if any(c.cap_applied and "unconfigured" in c.cap_applied for c in r.contributions)
        ]

        summary = RunSummary(
            provider_name=provider.name,
            accounts_discovered=result.accounts_discovered,
            accounts_rejected_by_hard_gates=result.accounts_rejected,
            accounts_researched=len(result.accounts_scored),
            classification_counts=dict(classification_counter),
            provider_errors=result.provider_errors,
            top_signals=signal_counter.most_common(10),
            top_pain_tracks=pain_track_counter.most_common(10),
            research_gaps=research_gaps,
        )
        write_run_summary(summary, EXPORTS_DIR / "run_summary.md")

    table = Table(title="Lead Radar demo run (mock provider)")
    table.add_column("Domain")
    table.add_column("Total score", justify="right")
    table.add_column("Classification")
    table.add_column("Status")
    for r in sorted(result.accounts_scored, key=lambda r: -r.score_run.total_score):
        table.add_row(
            r.account.domain,
            f"{r.score_run.total_score:.1f}",
            r.score_run.classification.value,
            r.account.status.value,
        )
    console.print(table)

    console.print(
        f"\n[green]Demo complete.[/green] Discovered {result.accounts_discovered}, "
        f"rejected {result.accounts_rejected} by hard gates, scored {len(result.accounts_scored)}."
    )
    console.print(f"Reports written to {EXPORTS_DIR}/:")
    for name in ("qualified_accounts.csv", "review_queue.csv", "evidence.jsonl", "run_summary.md"):
        console.print(f"  - {EXPORTS_DIR / name}")


if __name__ == "__main__":
    main()
