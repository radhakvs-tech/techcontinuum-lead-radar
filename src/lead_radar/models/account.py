"""Account, AccountAlias and CompanyMetric entities. Spec §3, §12."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from lead_radar.models.enums import AccountStatus, ARRConfidence


class Account(SQLModel, table=True):
    """A company under consideration. Deduplicated primarily by canonical domain."""

    id: int | None = Field(default=None, primary_key=True)

    company_name: str
    domain: str = Field(index=True, unique=True)

    headquarters_country: str | None = Field(default=None, index=True)
    employee_count: int | None = None

    # Revenue and ARR are stored separately and must never be conflated
    # (spec §3): reported figures, estimated ranges, and ARR estimates each
    # carry their own provenance and confidence.
    reported_revenue_usd: float | None = None
    revenue_min_usd: float | None = None
    revenue_max_usd: float | None = None
    estimated_arr_usd: float | None = None
    arr_estimation_method: str | None = None
    arr_confidence: ARRConfidence = ARRConfidence.UNKNOWN

    industry: str | None = None
    business_model: str | None = None
    company_type: str | None = Field(default=None, index=True)
    technologies: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    status: AccountStatus = Field(default=AccountStatus.DISCOVERED, index=True)

    # Conflicting or missing data is recorded here rather than silently
    # discarded or guessed away (spec §23 "Do not silently discard
    # conflicting data"). Surfaced verbatim in the `unknowns` report column.
    data_quality_flags: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AccountAlias(SQLModel, table=True):
    """Alternate domains/names an account is known by, for dedup safety net."""

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True)
    alias_domain: str | None = Field(default=None, index=True)
    alias_name: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CompanyMetric(SQLModel, table=True):
    """A single point-in-time metric observation (headcount, funding, etc.)."""

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True)

    metric_name: str
    metric_value: float | None = None
    metric_unit: str | None = None
    observed_date: date | None = None
    source_evidence_id: int | None = Field(default=None, foreign_key="evidence.id")

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
