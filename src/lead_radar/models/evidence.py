"""Evidence and Signal entities. Spec §5 (evidence hierarchy)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlmodel import Field, SQLModel

from lead_radar.models.enums import EvidenceClassification, EvidenceSourceType


class Evidence(SQLModel, table=True):
    """A single piece of material evidence backing a claim about an account.

    Every field here exists because a claim without it cannot be trusted:
    no URL/title means it cannot be checked, no dates mean recency cannot
    be judged, no independence_group means duplicate/syndicated sources
    could be double-counted as independent corroboration.
    """

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True)

    source_url: str
    source_title: str
    source_type: EvidenceSourceType
    published_date: date | None = None
    observed_date: date = Field(default_factory=lambda: datetime.now(UTC).date())

    evidence_text: str
    evidence_summary: str

    signal_type: str = Field(index=True)  # key into config/signal_taxonomy.yaml
    classification: EvidenceClassification = EvidenceClassification.UNKNOWN_REQUIRING_VALIDATION
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # Evidence sharing the same independence_group (e.g. the same press
    # release syndicated across outlets) counts as one signal, not many,
    # for the HIGH_INTENT independent-signal requirement (spec §5, §18.7).
    independence_group: str

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Signal(SQLModel, table=True):
    """A scoring-relevant signal instance detected from one or more Evidence rows."""

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True)
    evidence_id: int | None = Field(default=None, foreign_key="evidence.id")

    signal_key: str = Field(index=True)  # key into config/scoring.yaml `signals:`
    pain_track: str | None = None

    # The date used for recency decay. Missing dates must be handled
    # conservatively (spec §5, §18.15) — callers should treat None here as
    # "assume maximally stale" rather than "assume today".
    signal_date: date | None = None

    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    independence_group: str

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
