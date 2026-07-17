"""Lead Radar CLI. Spec §14 (Phase 1 command subset).

Real Vibe/web-research/LLM-backed commands (`enrich`, `research`,
`contacts discover`, `feedback import`, `dossier`) arrive in later phases.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import select

from lead_radar.db import get_session, init_db
from lead_radar.discovery import evaluate_hard_gates, run_discovery_pipeline
from lead_radar.discovery.ingest import ingest_company_record
from lead_radar.discovery.pipeline import REVIEW_REQUIRED_CLASSIFICATIONS
from lead_radar.models.account import Account
from lead_radar.models.enums import AccountStatus, ReviewerLabel
from lead_radar.models.evidence import Evidence, Signal
from lead_radar.models.scoring import ScoreContribution, ScoreRun
from lead_radar.providers import CsvProvider, MockProvider
from lead_radar.providers.base import CompanyDataProvider
from lead_radar.providers.credit_control import check_budget
from lead_radar.reporting import (
    RunSummary,
    build_qualified_account_row,
    write_evidence_jsonl,
    write_qualified_accounts_csv,
    write_review_queue_csv,
    write_run_summary,
)
from lead_radar.review.workflow import apply_review_decision
from lead_radar.scoring.engine import is_martech_account, score_account
from lead_radar.scoring.models import ScoreBreakdown, ScoredSignal
from lead_radar.scoring.offers import select_offer
from lead_radar.scoring.persistence import persist_score_run

app = typer.Typer(help="TechContinuum Lead Radar — evidence-driven B2B lead discovery and ranking.")
review_app = typer.Typer(help="Human-review workflow commands.")
app.add_typer(review_app, name="review")

console = Console()

EXPORTS_DIR = Path("data/exports")


def _get_provider(provider_name: str, csv_path: Path | None) -> CompanyDataProvider:
    if provider_name == "csv":
        if csv_path is None:
            raise typer.BadParameter("--csv-path is required when --provider csv is used")
        return CsvProvider(csv_path)
    if provider_name == "mock":
        return MockProvider()
    raise typer.BadParameter(
        f"Unsupported provider '{provider_name}'. Phase 1 supports: mock, csv."
    )


def _parse_countries(countries: str | None) -> list[str] | None:
    if not countries:
        return None
    return [c.strip().upper() for c in countries.split(",") if c.strip()]


@app.command("init-db")
def init_db_command() -> None:
    """Create the SQLite schema (idempotent)."""
    init_db()
    console.print("[green]Database initialised.[/green]")


@app.command("import-vibe-csv")
def import_vibe_csv_command(
    csv_path: Path = typer.Argument(..., help="Path to an exported Vibe CSV"),
) -> None:
    """Import companies from a CSV export. Idempotent: re-running updates
    existing accounts by domain rather than duplicating them."""
    provider = CsvProvider(csv_path)
    records = provider.search_companies()

    table = Table(title=f"Imported {len(records)} companies from {csv_path}")
    table.add_column("Domain")
    table.add_column("Status")

    with get_session() as session:
        for record in records:
            account = ingest_company_record(session, record)
            table.add_row(account.domain, account.status.value)

    console.print(table)


@app.command("discover")
def discover_command(
    countries: str = typer.Option(..., help="Comma-separated country codes, e.g. US,GB,DE,AU,SG"),
    provider: str = typer.Option("mock", help="Data provider: mock | csv"),
    csv_path: Path | None = typer.Option(None, help="Required when --provider csv"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Evaluate hard gates without writing to the database"
    ),
) -> None:
    """Search for companies and apply ICP hard gates."""
    country_list = _parse_countries(countries)
    data_provider = _get_provider(provider, csv_path)
    records = data_provider.search_companies(countries=country_list)

    table = Table(
        title=f"Discover ({'dry-run' if dry_run else 'persisted'}): {len(records)} companies found"
    )
    table.add_column("Domain")
    table.add_column("Passed hard gates?")
    table.add_column("Reasons / flags")

    if dry_run:
        for record in records:
            result = evaluate_hard_gates(record)
            reasons = "; ".join(result.rejection_reasons or result.data_quality_flags) or "-"
            table.add_row(record.domain, "yes" if result.passed else "no", reasons)
    else:
        with get_session() as session:
            for record in records:
                account = ingest_company_record(session, record)
                reasons = "; ".join(account.data_quality_flags) or "-"
                table.add_row(
                    account.domain,
                    "yes" if account.status != AccountStatus.REJECTED else "no",
                    reasons,
                )

    console.print(table)


@app.command("score")
def score_command(account_id: int = typer.Option(..., "--account-id")) -> None:
    """Re-run deterministic scoring for one account from its persisted evidence."""
    with get_session() as session:
        account = session.get(Account, account_id)
        if account is None:
            raise typer.BadParameter(f"No account with id {account_id}")

        signals = list(session.exec(select(Signal).where(Signal.account_id == account_id)))
        evidence_by_id = {
            e.id: e
            for e in session.exec(select(Evidence).where(Evidence.account_id == account_id))
            if e.id is not None
        }

        breakdown = score_account(account, signals, evidence_by_id)
        run = persist_score_run(session, breakdown)
        account.status = (
            AccountStatus.PENDING_HUMAN_REVIEW
            if breakdown.classification in REVIEW_REQUIRED_CLASSIFICATIONS
            else AccountStatus.SCORED
        )
        session.add(account)
        session.commit()

        table = Table(title=f"Score breakdown: {account.company_name} ({account.domain})")
        table.add_column("Signal")
        table.add_column("Dimension")
        table.add_column("Weight")
        table.add_column("Recency-adj.")
        table.add_column("Confidence")
        table.add_column("Contribution")
        table.add_column("Reason")
        for c in breakdown.signal_contributions:
            table.add_row(
                c.signal_key,
                c.dimension,
                f"{c.base_weight:+.1f}",
                f"{c.recency_adjusted_weight:+.2f}",
                f"{c.confidence:.2f}",
                f"{c.contribution:+.2f}",
                c.cap_applied or c.reason,
            )
        console.print(table)
        console.print(
            f"[bold]Total score:[/bold] {run.total_score:.2f}  "
            f"[bold]Classification:[/bold] {run.classification.value}  "
            f"[bold]Meets HIGH_INTENT evidence bar:[/bold] {run.meets_high_intent_evidence_bar}"
        )


@app.command("run")
def run_command(
    countries: str = typer.Option(..., help="Comma-separated country codes"),
    provider: str = typer.Option("mock", help="Data provider: mock | csv"),
    csv_path: Path | None = typer.Option(None, help="Required when --provider csv"),
    maximum_credits: float = typer.Option(0.0, "--maximum-credits"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    output_dir: Path = typer.Option(EXPORTS_DIR, "--output-dir"),
) -> None:
    """Run the full account-first pipeline and write all report outputs."""
    country_list = _parse_countries(countries)
    data_provider = _get_provider(provider, csv_path)

    budget_status = check_budget(estimated_credits=0.0, spent_this_run=0.0)
    console.print(
        f"[bold]Dry-run cost estimate:[/bold] 0.00 credits "
        f"(provider '{data_provider.name}' is free) — budget check: {budget_status.reason}"
    )
    if dry_run:
        records = data_provider.search_companies(countries=country_list)
        console.print(
            f"[yellow]Dry run:[/yellow] {len(records)} companies would be discovered. "
            "No data written."
        )
        return

    if maximum_credits < 0:
        raise typer.BadParameter("--maximum-credits must be >= 0")

    with get_session() as session:
        result = run_discovery_pipeline(session, data_provider, countries=country_list)

        rows = [
            build_qualified_account_row(
                r.account, r.score_run, r.contributions, r.primary_pain_track, r.recommended_offer
            )
            for r in result.accounts_scored
        ]
        write_qualified_accounts_csv(rows, output_dir / "qualified_accounts.csv")

        review_rows = [
            r for r in rows if r.review_status == AccountStatus.PENDING_HUMAN_REVIEW.value
        ]
        write_review_queue_csv(review_rows, output_dir / "review_queue.csv")

        write_evidence_jsonl(result.evidence_rows, output_dir / "evidence.jsonl")

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

        summary = RunSummary(
            provider_name=data_provider.name,
            accounts_discovered=result.accounts_discovered,
            accounts_rejected_by_hard_gates=result.accounts_rejected,
            accounts_researched=len(result.accounts_scored),
            classification_counts=dict(classification_counter),
            provider_errors=result.provider_errors,
            top_signals=signal_counter.most_common(10),
            top_pain_tracks=pain_track_counter.most_common(10),
        )
        write_run_summary(summary, output_dir / "run_summary.md")

    console.print(f"[green]Run complete.[/green] Reports written to {output_dir}/")
    console.print(
        f"Discovered {result.accounts_discovered}, rejected {result.accounts_rejected}, "
        f"scored {len(result.accounts_scored)}."
    )


@app.command("export")
def export_command(
    minimum_score: float = typer.Option(0.0, "--minimum-score"),
    fmt: str = typer.Option("csv", "--format"),
    output_path: Path = typer.Option(EXPORTS_DIR / "qualified_accounts.csv", "--output"),
) -> None:
    """Export previously scored accounts above a minimum score."""
    if fmt != "csv":
        raise typer.BadParameter("Phase 1 only supports --format csv")

    with get_session() as session:
        accounts = list(session.exec(select(Account)))
        rows = []
        for account in accounts:
            latest_run = session.exec(
                select(ScoreRun)
                .where(ScoreRun.account_id == account.id)
                .order_by(ScoreRun.run_at.desc())  # type: ignore[attr-defined]
            ).first()
            if latest_run is None or latest_run.total_score < minimum_score:
                continue
            contributions = list(
                session.exec(
                    select(ScoreContribution).where(ScoreContribution.score_run_id == latest_run.id)
                )
            )
            pain_track_signals = {
                "ai_transition_pressure": latest_run.ai_transition_score,
                "cloud_modernisation_pain": latest_run.cloud_modernisation_score,
                "martech_agentisation_pressure": latest_run.martech_pressure_score,
            }
            best_pain = max(pain_track_signals, key=lambda k: pain_track_signals[k])
            offer_code, _ = select_offer(
                _breakdown_from_run(latest_run, contributions), is_martech_account(account)
            )
            rows.append(
                build_qualified_account_row(
                    account, latest_run, contributions, best_pain, offer_code.value
                )
            )

    write_qualified_accounts_csv(rows, output_path)
    console.print(f"[green]Exported {len(rows)} accounts to {output_path}[/green]")


def _breakdown_from_run(run: ScoreRun, contributions: list[ScoreContribution]) -> ScoreBreakdown:
    return ScoreBreakdown(
        account_id=run.account_id,
        scoring_version=run.scoring_version,
        icp_score=run.icp_score,
        ai_transition_score=run.ai_transition_score,
        cloud_modernisation_score=run.cloud_modernisation_score,
        martech_pressure_score=run.martech_pressure_score,
        advisor_fit_score=run.advisor_fit_score,
        evidence_score=run.evidence_score,
        total_score=run.total_score,
        classification=run.classification,
        meets_high_intent_evidence_bar=run.meets_high_intent_evidence_bar,
        signal_contributions=[
            ScoredSignal(
                signal_key=c.signal_key,
                dimension=c.dimension,
                source=c.source,
                signal_date=c.signal_date,
                base_weight=c.original_weight,
                recency_adjusted_weight=c.recency_adjusted_weight,
                confidence=c.confidence,
                contribution=c.contribution,
                age_days=None,
                independence_group="",
                reason=c.reason,
                cap_applied=c.cap_applied,
            )
            for c in contributions
        ],
    )


@review_app.command("list")
def review_list_command() -> None:
    """List accounts pending human review."""
    with get_session() as session:
        accounts = list(
            session.exec(
                select(Account).where(Account.status == AccountStatus.PENDING_HUMAN_REVIEW)
            )
        )

    table = Table(title=f"{len(accounts)} accounts pending human review")
    table.add_column("ID")
    table.add_column("Company")
    table.add_column("Domain")
    table.add_column("Country")
    for account in accounts:
        table.add_row(
            str(account.id),
            account.company_name,
            account.domain,
            account.headquarters_country or "-",
        )
    console.print(table)


@review_app.command("approve")
def review_approve_command(
    account_id: int = typer.Argument(...),
    reason: str = typer.Option(..., "--reason"),
    reviewer: str = typer.Option("cli-user", "--reviewer"),
    label: ReviewerLabel | None = typer.Option(None, "--label"),
) -> None:
    """Approve an account for contact discovery (Phase 4 performs the actual fetch)."""
    with get_session() as session:
        account = session.get(Account, account_id)
        if account is None:
            raise typer.BadParameter(f"No account with id {account_id}")
        apply_review_decision(
            session, account, reviewer, AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY, reason, label
        )
    console.print(f"[green]Account {account_id} approved for contact discovery.[/green]")


@review_app.command("reject")
def review_reject_command(
    account_id: int = typer.Argument(...),
    reason: str = typer.Option(..., "--reason"),
    reviewer: str = typer.Option("cli-user", "--reviewer"),
    label: ReviewerLabel | None = typer.Option(None, "--label"),
) -> None:
    """Reject an account."""
    with get_session() as session:
        account = session.get(Account, account_id)
        if account is None:
            raise typer.BadParameter(f"No account with id {account_id}")
        apply_review_decision(session, account, reviewer, AccountStatus.REJECTED, reason, label)
    console.print(f"[green]Account {account_id} rejected.[/green]")


if __name__ == "__main__":
    app()
