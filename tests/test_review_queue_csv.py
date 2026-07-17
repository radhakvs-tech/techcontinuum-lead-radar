"""Confirms a hard-gate mismatch on a previously-approved account actually
reaches review_queue.csv output, not just the account record internally.
Spec §10, §15."""

from __future__ import annotations

import csv
from pathlib import Path

from sqlmodel import Session

from lead_radar.discovery.ingest import ingest_company_record
from lead_radar.models.enums import AccountStatus
from lead_radar.models.scoring import ScoreRun
from lead_radar.providers.base import ProviderCompanyRecord
from lead_radar.reporting.csv_export import write_review_queue_csv
from lead_radar.reporting.types import QualifiedAccountRow, build_qualified_account_row
from lead_radar.review.workflow import apply_review_decision


def _row(review_status: str, unknowns: str = "") -> QualifiedAccountRow:
    return QualifiedAccountRow(
        company="Example Co",
        domain="example.com",
        country="US",
        employee_count="100",
        revenue_range="reported:50,000,000",
        arr_confidence="UNKNOWN",
        industry="SaaS",
        primary_pain_track="A_ai_production_readiness",
        recommended_offer="offer_a",
        icp_score=20.0,
        ai_transition_score=10.0,
        cloud_modernisation_score=5.0,
        sector_pressure_score=0.0,
        advisor_fit_score=0.0,
        evidence_score=5.0,
        total_score=40.0,
        classification="WATCHLIST",
        top_signal_1="",
        top_signal_2="",
        top_signal_3="",
        signal_dates="unknown",
        evidence_urls="unknown",
        unknowns=unknowns,
        review_status=review_status,
        scoring_version="1.0.0",
    )


def test_write_review_queue_csv_still_includes_pending_human_review(tmp_path: Path) -> None:
    rows = [_row("PENDING_HUMAN_REVIEW")]
    write_review_queue_csv(rows, tmp_path / "review_queue.csv")
    with (tmp_path / "review_queue.csv").open() as f:
        written = list(csv.DictReader(f))
    assert len(written) == 1


def test_write_review_queue_csv_includes_approved_account_with_mismatch_flag(
    tmp_path: Path,
) -> None:
    rows = [
        _row(
            "APPROVED_FOR_CONTACT_DISCOVERY",
            unknowns="hard_gate_mismatch: new data fails hard gates (...) but human-reviewed "
            "status 'APPROVED_FOR_CONTACT_DISCOVERY' was preserved, not auto-overridden",
        )
    ]
    write_review_queue_csv(rows, tmp_path / "review_queue.csv")
    with (tmp_path / "review_queue.csv").open() as f:
        written = list(csv.DictReader(f))
    assert len(written) == 1
    assert "hard_gate_mismatch" in written[0]["unknowns"]
    assert written[0]["review_status"] == "APPROVED_FOR_CONTACT_DISCOVERY"


def test_write_review_queue_csv_excludes_approved_account_without_mismatch_flag(
    tmp_path: Path,
) -> None:
    """An approved account with no mismatch shouldn't clutter the review
    queue just because it once went through review — only PENDING or
    freshly-conflicting accounts belong there."""
    rows = [_row("APPROVED_FOR_CONTACT_DISCOVERY", unknowns="")]
    write_review_queue_csv(rows, tmp_path / "review_queue.csv")
    with (tmp_path / "review_queue.csv").open() as f:
        written = list(csv.DictReader(f))
    assert written == []


def test_end_to_end_mismatch_flag_reaches_review_queue_csv_file(
    session: Session, tmp_path: Path
) -> None:
    """Full path: ingest -> human-approve -> re-ingest with gate-failing
    data -> build the real QualifiedAccountRow -> write the real CSV ->
    read the actual file back. Not a mock of any of these steps."""
    record = ProviderCompanyRecord(
        company_name="Example Co",
        domain="example-co.example",
        headquarters_country="US",
        employee_count=100,
        reported_revenue_usd=50_000_000,
        company_type="b2b_saas",
    )
    account = ingest_company_record(session, record)
    apply_review_decision(
        session, account, "reviewer", AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY, "good fit"
    )

    conflicting_record = record.model_copy(update={"headquarters_country": "FR"})
    updated_account = ingest_company_record(session, conflicting_record)
    assert updated_account.status == AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY

    score_run = ScoreRun(account_id=updated_account.id, scoring_version="1.0.0", total_score=40.0)
    row = build_qualified_account_row(
        updated_account, score_run, [], "A_ai_production_readiness", "offer_a"
    )
    # Confirm build_qualified_account_row itself carries the flag through
    # from account.data_quality_flags into the row's `unknowns` field —
    # the step between the account record and the CSV row.
    assert "hard_gate_mismatch" in row.unknowns

    output_path = tmp_path / "review_queue.csv"
    write_review_queue_csv([row], output_path)

    with output_path.open() as f:
        written_rows = list(csv.DictReader(f))

    assert len(written_rows) == 1
    assert written_rows[0]["domain"] == "example-co.example"
    assert "hard_gate_mismatch" in written_rows[0]["unknowns"]
    assert written_rows[0]["review_status"] == "APPROVED_FOR_CONTACT_DISCOVERY"
