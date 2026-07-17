"""Converts provider CompanyEventRecords into persisted Evidence + Signal rows.

Phase 1 has no LLM (spec §17: the application must work in a deterministic
reduced-function mode without one), so provider events — which already
arrive as structured, provider-labelled data rather than free text — map
directly to evidence and signals. Free-text classification is Phase 3's
job, once a WebResearchProvider exists to fetch unstructured pages.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date

from sqlmodel import Session

from lead_radar.models.enums import EvidenceClassification, EvidenceSourceType
from lead_radar.models.evidence import Evidence, Signal
from lead_radar.providers.base import CompanyEventRecord

_SOURCE_TYPE_BY_EVENT_HINT: dict[str, EvidenceSourceType] = {
    "careers": EvidenceSourceType.CAREERS_PAGE,
    "press": EvidenceSourceType.PRESS_RELEASE,
    "changelog": EvidenceSourceType.CHANGELOG,
    "blog": EvidenceSourceType.ENGINEERING_BLOG,
}


def _guess_source_type(source_url: str | None) -> EvidenceSourceType:
    if source_url:
        for hint, source_type in _SOURCE_TYPE_BY_EVENT_HINT.items():
            if hint in source_url:
                return source_type
    return EvidenceSourceType.OTHER_PERMITTED_SOURCE


def _independence_group(event: CompanyEventRecord) -> str:
    """Events sharing the exact same source_url are the same corroborating
    source and must not be double-counted as independent signals (spec §5,
    §18.7). Events without a source_url are each treated as their own,
    unverifiable group."""
    if event.source_url:
        return hashlib.sha256(event.source_url.encode("utf-8")).hexdigest()[:16]
    return uuid.uuid4().hex


def event_to_evidence(account_id: int, event: CompanyEventRecord) -> Evidence:
    return Evidence(
        account_id=account_id,
        source_url=event.source_url or "unknown://no-source-provided",
        source_title=event.title,
        source_type=_guess_source_type(event.source_url),
        published_date=event.event_date,
        observed_date=event.event_date or date.today(),
        evidence_text=event.description,
        evidence_summary=event.title,
        signal_type=event.event_type,
        classification=EvidenceClassification.OBSERVED_FACT,
        confidence=event.confidence,
        independence_group=_independence_group(event),
    )


def event_to_signal(account_id: int, event: CompanyEventRecord, evidence_id: int | None) -> Signal:
    return Signal(
        account_id=account_id,
        evidence_id=evidence_id,
        signal_key=event.event_type,
        signal_date=event.event_date,
        confidence=event.confidence,
        independence_group=_independence_group(event),
    )


def ingest_events(
    session: Session, account_id: int, events: list[CompanyEventRecord]
) -> list[Signal]:
    """Persists one Evidence + one Signal row per event and returns the signals."""
    signals: list[Signal] = []
    for event in events:
        evidence = event_to_evidence(account_id, event)
        session.add(evidence)
        session.commit()
        session.refresh(evidence)

        signal = event_to_signal(account_id, event, evidence.id)
        session.add(signal)
        signals.append(signal)

    session.commit()
    for signal in signals:
        session.refresh(signal)
    return signals
