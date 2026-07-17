"""ResearchRun entity. Spec §7 (public web research — implemented in Phase 3)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class ResearchRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True)

    provider: str
    pages_fetched: int = 0
    status: str = "not_started"
    notes: str | None = None

    run_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
