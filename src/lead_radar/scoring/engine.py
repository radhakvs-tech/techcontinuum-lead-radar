"""Deterministic scoring engine. Spec §8.

Nothing here is an LLM call — every number is plain Python arithmetic over
config/scoring.yaml weights and Signal rows already persisted in the
database. This is intentional: spec §8 and §23 both forbid letting an LLM
invent the final score.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from lead_radar.models.account import Account
from lead_radar.models.enums import Classification
from lead_radar.models.evidence import Evidence, Signal
from lead_radar.scoring.models import ScoreBreakdown, ScoredSignal
from lead_radar.scoring.recency import recency_multiplier, resolve_age_and_confidence
from lead_radar.settings import get_icp_config, get_scoring_config, get_signal_taxonomy

# Company types treated as "martech" for the purpose of §8's non-martech
# reallocation rule. Kept narrower than icp.yaml's broader included types,
# which also cover adjacent-but-not-martech categories like enterprise
# software or research/customer-intelligence platforms.
MARTECH_COMPANY_TYPES = {
    "martech_saas",
    "marketing_automation",
    "customer_engagement",
    "conversational_marketing",
}


def is_martech_account(account: Account) -> bool:
    return account.company_type in MARTECH_COMPANY_TYPES


# spec §4E positive signal "50-200 employees" describes a structural account
# fact, not a dated event — there is no CompanyEventRecord for it, so unlike
# the other 18 external-advisor-likelihood signals it can never arrive via
# discovery/evidence_pipeline.ingest_events. It is derived directly from
# account.employee_count instead (see _employee_band_contribution).
STRUCTURAL_EMPLOYEE_BAND_SIGNAL = "employee_band_50_200"


def _employee_band_contribution(
    account: Account, signal_defs: dict[str, dict[str, Any]]
) -> ScoredSignal | None:
    cfg = signal_defs.get(STRUCTURAL_EMPLOYEE_BAND_SIGNAL)
    if cfg is None or account.employee_count is None:
        return None

    lo = float(cfg.get("min_employees", 50))
    hi = float(cfg.get("max_employees", 200))
    if not (lo <= account.employee_count <= hi):
        return None

    weight = float(cfg["weight"])
    return ScoredSignal(
        signal_key=STRUCTURAL_EMPLOYEE_BAND_SIGNAL,
        dimension=cfg["dimension"],
        source="account.employee_count",
        signal_date=None,
        base_weight=weight,
        recency_adjusted_weight=weight,
        confidence=1.0,
        contribution=weight,
        age_days=None,
        independence_group=f"structural:{STRUCTURAL_EMPLOYEE_BAND_SIGNAL}",
        reason=(
            f"employee_count={int(account.employee_count)} within advisor-fit "
            f"band [{lo:.0f}-{hi:.0f}] (spec §4E); structural account fact, "
            "not a dated event, so no recency decay applies"
        ),
        cap_applied=None,
    )


def dimension_max_points(is_martech: bool, scoring_config_data: dict[str, Any]) -> dict[str, float]:
    dims = {k: float(v) for k, v in scoring_config_data["dimensions"].items()}
    if is_martech:
        return dims

    targets: list[str] = scoring_config_data["non_martech_reallocation_targets"]
    martech_points = dims["martech_agentisation_pressure"]
    originals = {t: dims[t] for t in targets}
    total = sum(originals.values())

    for target in targets:
        dims[target] = originals[target] + martech_points * (originals[target] / total)
    dims["martech_agentisation_pressure"] = 0.0
    return dims


def _icp_fit_score(account: Account, max_points: float) -> float:
    icp = get_icp_config()
    commercial = icp["commercial_size"]
    included_types = set(icp.get("included_company_types", []))

    if account.reported_revenue_usd is None:
        revenue_fit = 0.6  # unknown, not penalised as heavily as being genuinely out of band
    elif (
        commercial["minimum_revenue_usd"]
        <= account.reported_revenue_usd
        <= commercial["maximum_revenue_usd"]
    ):
        revenue_fit = 1.0
    else:
        revenue_fit = 0.3

    type_fit = 1.0 if account.company_type in included_types else 0.5

    return round(max_points * ((revenue_fit + type_fit) / 2), 2)


def _intent_signal_contributions(contributions: list[ScoredSignal]) -> list[ScoredSignal]:
    """Positive contributions that count as evidence-backed *intent* signals
    for spec §5's evidence-quality rules (independent signals, recency,
    direct commitment). Excludes the structural employee-band-50-200 signal:
    it is an ICP/advisor-fit fact derived from account.employee_count, not
    dated evidence of intent, so it must not inflate the independent-signal
    count or the HIGH_INTENT evidence bar."""
    return [
        c
        for c in contributions
        if c.contribution > 0 and c.signal_key != STRUCTURAL_EMPLOYEE_BAND_SIGNAL
    ]


def _evidence_quality_score(
    contributions: list[ScoredSignal],
    max_points: float,
) -> float:
    positive = _intent_signal_contributions(contributions)
    if not positive:
        return 0.0

    independent_groups = {c.independence_group for c in positive}
    independence_ratio = min(1.0, len(independent_groups) / 3)

    recent = [c for c in positive if c.age_days is not None and c.age_days <= 90]
    recency_ratio = 1.0 if recent else 0.0

    avg_confidence = sum(c.confidence for c in positive) / len(positive)

    combined = 0.4 * independence_ratio + 0.3 * recency_ratio + 0.3 * avg_confidence
    return round(max_points * combined, 2)


def _meets_high_intent_bar(
    contributions: list[ScoredSignal],
    direct_commitment_keys: set[str],
    requirements: dict[str, Any],
) -> bool:
    positive = _intent_signal_contributions(contributions)
    independent_groups = {c.independence_group for c in positive}
    direct_commitment = [c for c in positive if c.signal_key in direct_commitment_keys]
    recent_material = [
        c
        for c in positive
        if c.age_days is not None
        and c.age_days <= requirements["maximum_days_since_most_recent_material_signal"]
    ]
    return (
        len(independent_groups) >= requirements["minimum_independent_signals"]
        and len(direct_commitment) >= requirements["minimum_direct_commitment_signals"]
        and len(recent_material) >= 1
    )


def _classify(
    total_score: float,
    meets_high_intent_bar: bool,
    icp_score: float,
    icp_max_points: float,
    contributions: list[ScoredSignal],
    thresholds: dict[str, Any],
) -> Classification:
    positive_material = [
        c
        for c in _intent_signal_contributions(contributions)
        if c.dimension != "unscored"
    ]

    if total_score >= thresholds["high_intent"]:
        return (
            Classification.HIGH_INTENT
            if meets_high_intent_bar
            else Classification.HIGH_PRIORITY_REVIEW
        )
    if total_score >= thresholds["high_priority_review"]:
        return Classification.HIGH_PRIORITY_REVIEW
    if total_score >= thresholds["watchlist"]:
        return Classification.WATCHLIST
    if not positive_material:
        if icp_score >= icp_max_points * 0.75:
            return Classification.GOOD_FIT_LOW_SIGNAL
        return Classification.INSUFFICIENT_INFORMATION
    return Classification.IGNORE_WEAK_SIGNAL


def score_account(
    account: Account,
    signals: list[Signal],
    evidence_by_id: dict[int, Evidence],
    today: date | None = None,
) -> ScoreBreakdown:
    if account.id is None:
        raise ValueError("account must be persisted (have an id) before scoring")

    scoring_config = get_scoring_config()
    scoring_data = scoring_config.data
    taxonomy = get_signal_taxonomy()
    today = today or date.today()

    signal_defs: dict[str, dict[str, Any]] = scoring_data["signals"]
    direct_commitment_keys = set(taxonomy.get("direct_commitment_signals", []))

    is_martech = is_martech_account(account)
    max_points = dimension_max_points(is_martech, scoring_data)

    raw_by_dimension: dict[str, float] = dict.fromkeys(max_points, 0.0)
    contributions: list[ScoredSignal] = []

    for signal in signals:
        cfg = signal_defs.get(signal.signal_key)
        source = "unknown"
        if signal.evidence_id is not None and signal.evidence_id in evidence_by_id:
            source = evidence_by_id[signal.evidence_id].source_url

        if cfg is None:
            contributions.append(
                ScoredSignal(
                    signal_key=signal.signal_key,
                    dimension="unscored",
                    source=source,
                    signal_date=signal.signal_date,
                    base_weight=0.0,
                    recency_adjusted_weight=0.0,
                    confidence=signal.confidence,
                    contribution=0.0,
                    age_days=None,
                    independence_group=signal.independence_group,
                    reason=f"'{signal.signal_key}' has no configured weight in scoring.yaml",
                    cap_applied="unconfigured signal — no score effect",
                )
            )
            continue

        base_weight = float(cfg["weight"])
        half_life_days = float(cfg["half_life_days"])
        dimension = cfg["dimension"]

        age_days, confidence = resolve_age_and_confidence(
            signal.signal_date, half_life_days, signal.confidence, today
        )
        recency_adjusted = base_weight * confidence * recency_multiplier(age_days, half_life_days)

        cap_applied: str | None = None
        if dimension == "martech_agentisation_pressure" and not is_martech:
            cap_applied = (
                "martech dimension reallocated for non-martech account — excluded from totals"
            )

        contribution_value = 0.0 if cap_applied else recency_adjusted
        raw_by_dimension[dimension] = raw_by_dimension.get(dimension, 0.0) + contribution_value

        date_desc = (
            "unknown date (treated conservatively)"
            if signal.signal_date is None
            else f"{age_days}d ago"
        )
        contributions.append(
            ScoredSignal(
                signal_key=signal.signal_key,
                dimension=dimension,
                source=source,
                signal_date=signal.signal_date,
                base_weight=base_weight,
                recency_adjusted_weight=recency_adjusted,
                confidence=confidence,
                contribution=contribution_value,
                age_days=age_days,
                independence_group=signal.independence_group,
                reason=(
                    f"base weight {base_weight:+.1f}, {date_desc}, confidence {confidence:.2f}, "
                    f"half-life {half_life_days:.0f}d"
                ),
                cap_applied=cap_applied,
            )
        )

    employee_band_signal = _employee_band_contribution(account, signal_defs)
    if employee_band_signal is not None:
        contributions.append(employee_band_signal)
        raw_by_dimension[employee_band_signal.dimension] = (
            raw_by_dimension.get(employee_band_signal.dimension, 0.0)
            + employee_band_signal.contribution
        )

    dimension_scores: dict[str, float] = {}
    for dimension, cap in max_points.items():
        if dimension in ("icp_and_commercial_fit", "evidence_quality_and_recency"):
            continue
        dimension_scores[dimension] = max(0.0, min(raw_by_dimension.get(dimension, 0.0), cap))

    dimension_scores["icp_and_commercial_fit"] = _icp_fit_score(
        account, max_points["icp_and_commercial_fit"]
    )
    dimension_scores["evidence_quality_and_recency"] = _evidence_quality_score(
        contributions, max_points["evidence_quality_and_recency"]
    )

    total_score = round(sum(dimension_scores.values()), 2)
    meets_bar = _meets_high_intent_bar(
        contributions, direct_commitment_keys, scoring_data["high_intent_requirements"]
    )
    classification = _classify(
        total_score,
        meets_bar,
        dimension_scores["icp_and_commercial_fit"],
        max_points["icp_and_commercial_fit"],
        contributions,
        scoring_data["classification"],
    )

    return ScoreBreakdown(
        account_id=account.id,
        scoring_version=scoring_data["scoring_version"],
        icp_score=dimension_scores["icp_and_commercial_fit"],
        ai_transition_score=dimension_scores.get("ai_transition_pressure", 0.0),
        cloud_modernisation_score=dimension_scores.get("cloud_modernisation_pain", 0.0),
        martech_pressure_score=dimension_scores.get("martech_agentisation_pressure", 0.0),
        advisor_fit_score=dimension_scores.get("external_advisor_likelihood", 0.0),
        evidence_score=dimension_scores["evidence_quality_and_recency"],
        total_score=total_score,
        classification=classification,
        meets_high_intent_evidence_bar=meets_bar,
        signal_contributions=contributions,
    )
