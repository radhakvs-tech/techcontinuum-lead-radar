"""ProviderUsage entity. Spec §6 (credit controls / usage tracking)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class ProviderUsage(SQLModel, table=True):
    """A logged call to any CompanyDataProvider operation, for credit tracking
    and idempotent-retry auditing."""

    id: int | None = Field(default=None, primary_key=True)

    provider_name: str
    operation: str
    account_id: int | None = Field(default=None, foreign_key="account.id")

    credits_estimated: float | None = None
    credits_actual: float | None = None

    success: bool = True
    error_message: str | None = None

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
