"""Spec §14 CLI. Acceptance #20 (CLI produces a useful dry-run report)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from lead_radar.cli import app
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
