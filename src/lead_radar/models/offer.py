"""OfferRecommendation entity. Spec §9 (recommended offer matching)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from lead_radar.models.enums import OfferCode


class OfferRecommendation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True)
    score_run_id: int | None = Field(default=None, foreign_key="scorerun.id")

    offer_code: OfferCode
    rationale: str

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
