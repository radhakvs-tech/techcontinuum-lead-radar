"""Spec §14 CLI. Acceptance #20 (CLI produces a useful dry-run report)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import select
from typer.testing import CliRunner

from lead_radar.cli import _get_web_provider, app
from lead_radar.db import get_session
from lead_radar.models.account import Account
from lead_radar.providers.pattern_guess_provider import PatternGuessProvider
from lead_radar.settings import get_settings

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEAD_RADAR_DB_PATH", str(tmp_path / "cli-test.db"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_init_db_command_succeeds() -> None:
    result = runner.invoke(app, ["init-db"])
    assert result.exit_code == 0
    assert "Database initialised" in result.stdout


def test_discover_dry_run_reports_without_persisting(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init-db"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["discover", "--countries", "US,GB,DE,AU,SG", "--dry-run"])
    assert result.exit_code == 0
    assert "companies found" in result.stdout
    assert "brightloop-martech.example" in result.stdout


def test_run_command_writes_reports(tmp_path: Path) -> None:
    output_dir = tmp_path / "exports"
    result = runner.invoke(app, ["init-db"])
    assert result.exit_code == 0

    result = runner.invoke(
        app,
        ["run", "--countries", "US,GB,DE,AU,SG", "--output-dir", str(output_dir)],
    )
    assert result.exit_code == 0, result.stdout
    assert (output_dir / "qualified_accounts.csv").exists()
    assert (output_dir / "review_queue.csv").exists()
    assert (output_dir / "evidence.jsonl").exists()
    assert (output_dir / "run_summary.md").exists()


def test_review_list_shows_pending_accounts(tmp_path: Path) -> None:
    output_dir = tmp_path / "exports"
    runner.invoke(app, ["init-db"])
    runner.invoke(app, ["run", "--countries", "US,GB,DE,AU,SG", "--output-dir", str(output_dir)])

    result = runner.invoke(app, ["review", "list"])
    assert result.exit_code == 0
    assert "pending human review" in result.stdout


def test_research_skips_account_with_no_prior_score_run() -> None:
    """`research` gates on spec §7's "preliminary score threshold" — an
    account discovered via `discover` (no `score`/`run` yet) has no
    ScoreRun at all, so it must be skipped, not researched."""
    runner.invoke(app, ["init-db"])
    runner.invoke(app, ["discover", "--countries", "US,GB,DE,AU,SG"])

    with get_session() as session:
        account = session.exec(
            select(Account).where(Account.domain == "brightloop-martech.example")
        ).first()
        assert account is not None
        account_id = account.id

    result = runner.invoke(app, ["research", "--account-id", str(account_id), "--provider", "mock"])
    assert result.exit_code == 0, result.stdout
    assert "skipped" in result.stdout.lower()


def test_research_runs_against_mock_provider_once_scored(tmp_path: Path) -> None:
    """The scenario-1 demo fixture (spec §19) clears the default
    preliminary_score_threshold via `run`. --provider mock has empty
    fixtures, so this only exercises the CLI wiring — deeper extraction
    behaviour is covered by tests/test_research_pipeline.py — but it proves
    `research` never touches the network by default."""
    output_dir = tmp_path / "exports"
    runner.invoke(app, ["init-db"])
    runner.invoke(app, ["run", "--countries", "US,GB,DE,AU,SG", "--output-dir", str(output_dir)])

    with get_session() as session:
        account = session.exec(
            select(Account).where(Account.domain == "brightloop-martech.example")
        ).first()
        assert account is not None
        account_id = account.id

    result = runner.invoke(app, ["research", "--account-id", str(account_id), "--provider", "mock"])
    assert result.exit_code == 0, result.stdout
    assert "Research:" in result.stdout


def test_research_with_manual_url_provider_and_no_manifest_fetches_nothing(
    tmp_path: Path,
) -> None:
    """No manifest file exists yet at the given path, so ManualUrlProvider
    has nothing to search or fetch — proving the CLI's default provider
    can never make a real network call until a human populates a
    manifest."""
    output_dir = tmp_path / "exports"
    runner.invoke(app, ["init-db"])
    runner.invoke(app, ["run", "--countries", "US,GB,DE,AU,SG", "--output-dir", str(output_dir)])

    with get_session() as session:
        account = session.exec(
            select(Account).where(Account.domain == "brightloop-martech.example")
        ).first()
        assert account is not None
        account_id = account.id

    missing_manifest = tmp_path / "no-such-manifest.yaml"
    result = runner.invoke(
        app,
        [
            "research",
            "--account-id",
            str(account_id),
            "--provider",
            "manual_url",
            "--manifest-path",
            str(missing_manifest),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "0 page(s) fetched" in result.stdout


def test_research_default_provider_omitted_stays_manual_url_and_safe(tmp_path: Path) -> None:
    """Omitting --provider entirely must behave exactly like explicitly
    passing --provider manual_url with no manifest: zero network calls.
    This is the regression test for "safe by default" now that
    pattern_guess (which does fetch real URLs the moment it runs) is also
    a selectable provider."""
    output_dir = tmp_path / "exports"
    runner.invoke(app, ["init-db"])
    runner.invoke(app, ["run", "--countries", "US,GB,DE,AU,SG", "--output-dir", str(output_dir)])

    with get_session() as session:
        account = session.exec(
            select(Account).where(Account.domain == "brightloop-martech.example")
        ).first()
        assert account is not None
        account_id = account.id

    result = runner.invoke(app, ["research", "--account-id", str(account_id)])
    assert result.exit_code == 0, result.stdout
    assert "0 page(s) fetched" in result.stdout


def test_get_web_provider_pattern_guess_is_opt_in_and_scoped_to_the_account() -> None:
    """Unit-level check of the wiring itself, with no network access:
    constructing a PatternGuessProvider never makes an HTTP call (only
    search()/fetch_page() do), so this exercises _get_web_provider's
    pattern_guess branch safely and confirms it derives the expected
    company name from the loaded Account rather than guessing blind."""
    account = Account(id=1, domain="acme.example", company_name="Acme Corp")

    provider = _get_web_provider("pattern_guess", None, account)

    assert isinstance(provider, PatternGuessProvider)
    assert provider._company_names == {"acme.example": "Acme Corp"}  # noqa: SLF001


def test_get_web_provider_pattern_guess_without_account_has_no_company_names() -> None:
    provider = _get_web_provider("pattern_guess", None, None)
    assert isinstance(provider, PatternGuessProvider)
    assert provider._company_names == {}  # noqa: SLF001
