"""CsvProvider — reads an exported Vibe (or hand-built) CSV of companies.

Expected columns (extra columns are ignored, missing optional columns are
treated as unknown rather than rejecting the row):
company_name, domain, headquarters_country, employee_count,
reported_revenue, industry, business_model, company_type, technologies

`technologies` is a single field with values separated by `;`.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from lead_radar.providers.base import (
    CompanyEventRecord,
    ContactRecord,
    CostEstimate,
    ProviderCompanyRecord,
)


class CsvImportError(Exception):
    """Raised when a CSV file is missing required columns."""


REQUIRED_COLUMNS = {"company_name", "domain"}


def _parse_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    return int(float(value))


def _parse_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    return float(value)


def load_companies_from_csv(path: Path) -> list[ProviderCompanyRecord]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            raise CsvImportError(f"CSV {path} is missing required columns: {sorted(missing)}")

        records = []
        for row in reader:
            technologies = [
                t.strip() for t in (row.get("technologies") or "").split(";") if t.strip()
            ]
            records.append(
                ProviderCompanyRecord(
                    company_name=row["company_name"].strip(),
                    domain=row["domain"].strip().lower(),
                    headquarters_country=(row.get("headquarters_country") or "").strip() or None,
                    employee_count=_parse_int(row.get("employee_count")),
                    reported_revenue_usd=_parse_float(row.get("reported_revenue")),
                    industry=(row.get("industry") or "").strip() or None,
                    business_model=(row.get("business_model") or "").strip() or None,
                    company_type=(row.get("company_type") or "").strip() or None,
                    technologies=technologies,
                )
            )
        return records


class CsvProvider:
    """CompanyDataProvider backed by a static, pre-loaded CSV file. Free (0 credits)."""

    name = "csv"

    def __init__(self, csv_path: Path) -> None:
        self._companies: dict[str, ProviderCompanyRecord] = {
            record.domain: record for record in load_companies_from_csv(csv_path)
        }

    def estimate_query_cost(self, operation: str, **params: Any) -> CostEstimate:
        return CostEstimate(
            operation=operation, estimated_credits=0.0, notes="csv provider is free"
        )

    def company_statistics(self, **filters: Any) -> dict[str, Any]:
        return {"total_companies": len(self._companies)}

    def search_companies(self, **filters: Any) -> list[ProviderCompanyRecord]:
        countries = filters.get("countries")
        results = list(self._companies.values())
        if countries:
            results = [c for c in results if c.headquarters_country in countries]
        return results

    def enrich_company(self, domain: str) -> ProviderCompanyRecord | None:
        return self._companies.get(domain)

    def get_company_events(self, domain: str) -> list[CompanyEventRecord]:
        return []

    def find_contacts(self, domain: str) -> list[ContactRecord]:
        return []

    def enrich_contact_email(self, contact: ContactRecord) -> ContactRecord:
        return contact
