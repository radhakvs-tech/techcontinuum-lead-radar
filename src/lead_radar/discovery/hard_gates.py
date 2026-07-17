"""ICP hard gates. Spec §3, §18.1-3.

Geography and employee-band violations are hard rejections. Revenue/ARR
being missing or outside the target band is recorded as a data-quality
flag, never a rejection — spec §3 is explicit that missing ARR must not
auto-reject an otherwise strong company.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from lead_radar.providers.base import ProviderCompanyRecord
from lead_radar.settings import YamlConfig, get_exclusions_config, get_icp_config


class HardGateResult(BaseModel):
    passed: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    data_quality_flags: list[str] = Field(default_factory=list)


def evaluate_hard_gates(
    record: ProviderCompanyRecord,
    icp_config: YamlConfig | None = None,
    exclusions_config: YamlConfig | None = None,
) -> HardGateResult:
    icp = icp_config or get_icp_config()
    exclusions = exclusions_config or get_exclusions_config()

    reasons: list[str] = []
    flags: list[str] = []

    allowed_countries = icp["geography"]["allowed_countries"]
    if record.headquarters_country not in allowed_countries:
        reasons.append(
            f"headquarters_country '{record.headquarters_country}' is outside the "
            f"configured geography {allowed_countries}"
        )

    size = icp["company_size"]
    min_employees = size["minimum_employees"]
    max_employees = size["maximum_employees"]
    if record.employee_count is None:
        flags.append("employee_count is unknown")
    elif record.employee_count < min_employees:
        reasons.append(
            f"employee_count {record.employee_count} is below the minimum {min_employees}"
        )
    elif record.employee_count > max_employees:
        reasons.append(
            f"employee_count {record.employee_count} is above the maximum {max_employees}"
        )

    commercial = icp["commercial_size"]
    if record.reported_revenue_usd is None:
        flags.append("reported_revenue_usd is unknown")
    elif not (
        commercial["minimum_revenue_usd"]
        <= record.reported_revenue_usd
        <= commercial["maximum_revenue_usd"]
    ):
        min_rev = commercial["minimum_revenue_usd"]
        max_rev = commercial["maximum_revenue_usd"]
        flags.append(
            f"reported_revenue_usd {record.reported_revenue_usd:,.0f} is outside the target "
            f"band [{min_rev:,.0f}, {max_rev:,.0f}]"
        )

    included_types = set(icp.get("included_company_types", []))
    excluded_types = set(icp.get("excluded_company_types", []))
    if record.company_type in excluded_types:
        reasons.append(f"company_type '{record.company_type}' is explicitly excluded")
    elif included_types and record.company_type not in included_types:
        flags.append(f"company_type '{record.company_type}' is not in the included-types list")

    haystack = " ".join(
        filter(None, [record.industry, record.company_type, " ".join(record.technologies)])
    ).lower()
    for keyword in exclusions.get("industry_keyword_excludes", []):
        if keyword.lower() in haystack:
            reasons.append(f"industry/company-type text matched excluded keyword '{keyword}'")
            break

    return HardGateResult(
        passed=len(reasons) == 0, rejection_reasons=reasons, data_quality_flags=flags
    )
