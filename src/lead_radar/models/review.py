"""HumanReview entity. Spec §10 (human-review workflow)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from lead_radar.models.enums import AccountStatus, ReviewerLabel


class HumanReview(SQLModel, table=True):
    """An audit-logged human decision that changed an account's status."""

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True)

    reviewer: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    old_status: AccountStatus
    new_status: AccountStatus
    reviewer_label: ReviewerLabel | None = None
    reason: str

    scoring_version: str | None = None
