"""Converts provider records into Account rows: dedup by canonical domain,
conflicting-data detection, and hard-gate application. Spec §3, §12, §18.14.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, select

from lead_radar.discovery.hard_gates import evaluate_hard_gates
from lead_radar.models.account import Account
from lead_radar.models.enums import AccountStatus, ARRConfidence
from lead_radar.providers.base import ProviderCompanyRecord

# A conflict is only flagged when the reported figure falls outside the
# estimated range by more than this tolerance, so ordinary estimation noise
# isn't mistaken for a genuine data conflict.
REVENUE_CONFLICT_TOLERANCE = 0.25


def canonicalize_domain(domain: str) -> str:
    d = domain.strip().lower()
    for prefix in ("https://", "http://"):
        if d.startswith(prefix):
            d = d[len(prefix) :]
    d = d.removeprefix("www.")
    return d.rstrip("/").split("/")[0]


def _detect_revenue_conflict(
    record: ProviderCompanyRecord,
) -> tuple[float | None, float | None, list[str]]:
    """Returns (estimated_min, estimated_max, flags)."""
    flags: list[str] = []
    est_min = record.raw.get("estimated_revenue_min_usd")
    est_max = record.raw.get("estimated_revenue_max_usd")
    if record.reported_revenue_usd is not None and est_min is not None and est_max is not None:
        tolerance_low = est_min * (1 - REVENUE_CONFLICT_TOLERANCE)
        tolerance_high = est_max * (1 + REVENUE_CONFLICT_TOLERANCE)
        if not (tolerance_low <= record.reported_revenue_usd <= tolerance_high):
            flags.append(
                f"reported_revenue_usd ({record.reported_revenue_usd:,.0f}) conflicts with "
                f"estimated_revenue range ({est_min:,.0f}-{est_max:,.0f}); both are retained, "
                "arr_confidence downgraded"
            )
    return est_min, est_max, flags


def ingest_company_record(session: Session, record: ProviderCompanyRecord) -> Account:
    """Upsert a provider record into an Account. Idempotent: re-ingesting the
    same domain updates the existing row instead of creating a duplicate
    (spec §12 dedup, §18.14 duplicate domains merge safely, §22 idempotent imports)."""
    domain = canonicalize_domain(record.domain)

    existing = session.exec(select(Account).where(Account.domain == domain)).first()

    gate_result = evaluate_hard_gates(record)
    est_min, est_max, conflict_flags = _detect_revenue_conflict(record)

    rejection_flags = [f"hard_gate_rejected: {reason}" for reason in gate_result.rejection_reasons]
    data_quality_flags = list(gate_result.data_quality_flags) + conflict_flags + rejection_flags
    arr_confidence = ARRConfidence.LOW if conflict_flags else ARRConfidence.UNKNOWN

    account = existing or Account(domain=domain, company_name=record.company_name)
    account.company_name = record.company_name
    account.headquarters_country = record.headquarters_country
    account.employee_count = record.employee_count
    account.reported_revenue_usd = record.reported_revenue_usd
    account.revenue_min_usd = est_min
    account.revenue_max_usd = est_max
    account.arr_confidence = arr_confidence
    account.industry = record.industry
    account.business_model = record.business_model
    account.company_type = record.company_type
    account.technologies = record.technologies
    account.data_quality_flags = data_quality_flags
    account.status = (
        AccountStatus.PRELIMINARY_QUALIFIED if gate_result.passed else AccountStatus.REJECTED
    )
    account.updated_at = datetime.now(UTC)

    session.add(account)
    session.commit()
    session.refresh(account)
    return account
