"""Spec §3, §18 acceptance criteria 1-3."""

from __future__ import annotations

from lead_radar.discovery.hard_gates import evaluate_hard_gates
from lead_radar.providers.base import ProviderCompanyRecord


def _record(**overrides: object) -> ProviderCompanyRecord:
    defaults = dict(
        company_name="Test Co",
        domain="test-co.example",
        headquarters_country="US",
        employee_count=100,
        reported_revenue_usd=50_000_000,
        company_type="b2b_saas",
        industry="B2B SaaS",
    )
    defaults.update(overrides)
    return ProviderCompanyRecord(**defaults)  # type: ignore[arg-type]


def test_company_outside_geography_is_rejected() -> None:
    result = evaluate_hard_gates(_record(headquarters_country="FR"))
    assert result.passed is False
    assert any("geography" in r for r in result.rejection_reasons)


def test_company_below_employee_band_is_rejected() -> None:
    result = evaluate_hard_gates(_record(employee_count=10))
    assert result.passed is False
    assert any("below the minimum" in r for r in result.rejection_reasons)


def test_company_above_employee_band_is_rejected() -> None:
    result = evaluate_hard_gates(_record(employee_count=5000))
    assert result.passed is False
    assert any("above the maximum" in r for r in result.rejection_reasons)


def test_missing_arr_does_not_reject() -> None:
    result = evaluate_hard_gates(_record(reported_revenue_usd=None))
    assert result.passed is True
    assert any("revenue" in f for f in result.data_quality_flags)


def test_revenue_out_of_band_flags_but_does_not_reject() -> None:
    result = evaluate_hard_gates(_record(reported_revenue_usd=900_000_000))
    assert result.passed is True
    assert any("outside the target band" in f for f in result.data_quality_flags)


def test_excluded_company_type_is_rejected() -> None:
    result = evaluate_hard_gates(_record(company_type="recruitment_staffing"))
    assert result.passed is False
    assert any("explicitly excluded" in r for r in result.rejection_reasons)


def test_excluded_keyword_in_industry_text_is_rejected() -> None:
    result = evaluate_hard_gates(_record(company_type="b2b_saas", industry="Marketing Agency"))
    assert result.passed is False


def test_missing_data_never_uses_negative_absence_wording() -> None:
    """Spec §18.19 / §23: flags about missing data must not assert the
    company lacks something — only that it is unknown."""
    result = evaluate_hard_gates(_record(reported_revenue_usd=None))
    for flag in result.data_quality_flags:
        assert "lacks" not in flag.lower()
        assert "does not have" not in flag.lower()
        assert "no evaluation" not in flag.lower()
