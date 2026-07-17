"""Spec §6 CsvProvider, §22 idempotent imports."""

from __future__ import annotations

from pathlib import Path

import pytest

from lead_radar.discovery.ingest import ingest_company_record
from lead_radar.providers.csv_provider import CsvImportError, CsvProvider, load_companies_from_csv


def _write_csv(path: Path, rows: list[str]) -> Path:
    header = (
        "company_name,domain,headquarters_country,employee_count,reported_revenue,"
        "industry,business_model,company_type,technologies"
    )
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


def test_loads_valid_csv(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path / "companies.csv",
        ["Example Co,example-co.example,US,120,45000000,B2B SaaS,B2B SaaS,b2b_saas,AWS;Kubernetes"],
    )
    records = load_companies_from_csv(csv_path)
    assert len(records) == 1
    assert records[0].domain == "example-co.example"
    assert records[0].technologies == ["AWS", "Kubernetes"]


def test_missing_required_columns_raises(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("company_name\nExample Co\n", encoding="utf-8")
    with pytest.raises(CsvImportError):
        load_companies_from_csv(csv_path)


def test_missing_optional_fields_are_treated_as_unknown(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path / "companies.csv", ["Example Co,example-co.example,,,,,,,"])
    records = load_companies_from_csv(csv_path)
    assert records[0].employee_count is None
    assert records[0].reported_revenue_usd is None


def test_reimporting_same_csv_does_not_duplicate_accounts(tmp_path: Path, session) -> None:
    csv_path = _write_csv(
        tmp_path / "companies.csv",
        ["Example Co,example-co.example,US,120,45000000,B2B SaaS,B2B SaaS,b2b_saas,AWS"],
    )
    provider = CsvProvider(csv_path)
    records = provider.search_companies()

    for _ in range(3):
        for record in records:
            ingest_company_record(session, record)

    from sqlmodel import select

    from lead_radar.models.account import Account

    accounts = list(session.exec(select(Account)))
    assert len(accounts) == 1
