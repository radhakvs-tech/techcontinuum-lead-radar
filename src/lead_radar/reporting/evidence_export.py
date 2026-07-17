"""evidence.jsonl writer. Spec §15."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lead_radar.models.account import Account
from lead_radar.models.evidence import Evidence


def evidence_to_dict(evidence: Evidence, account_domain: str) -> dict[str, Any]:
    return {
        "account_domain": account_domain,
        "evidence_id": evidence.id,
        "source_url": evidence.source_url,
        "source_title": evidence.source_title,
        "source_type": evidence.source_type.value,
        "published_date": evidence.published_date.isoformat() if evidence.published_date else None,
        "observed_date": evidence.observed_date.isoformat(),
        "evidence_text": evidence.evidence_text,
        "evidence_summary": evidence.evidence_summary,
        "signal_type": evidence.signal_type,
        "classification": evidence.classification.value,
        "confidence": evidence.confidence,
        "independence_group": evidence.independence_group,
    }


def write_evidence_jsonl(rows: list[tuple[Evidence, Account]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for evidence, account in rows:
            f.write(json.dumps(evidence_to_dict(evidence, account.domain)) + "\n")
