"""Spec §6 credit controls. Acceptance #9."""

from __future__ import annotations

import pytest

from lead_radar.providers.credit_control import (
    CreditBudgetExceededError,
    check_budget,
    require_budget,
)
from lead_radar.settings import YamlConfig


def _providers_config(maximum_per_run: float) -> YamlConfig:
    return YamlConfig(
        data={
            "credit_budget": {
                "maximum_per_run": maximum_per_run,
                "maximum_per_week": maximum_per_run * 4,
                "require_cost_estimate": True,
                "retrieve_contacts_only_after_approval": True,
                "retrieve_email_only_after_approval": True,
                "retrieve_phone_numbers": False,
            }
        }
    )


def test_default_zero_budget_refuses_any_paid_operation() -> None:
    config = _providers_config(maximum_per_run=0)
    status = check_budget(estimated_credits=1.0, spent_this_run=0.0, providers_config=config)
    assert status.allowed is False


def test_free_operation_is_allowed_even_with_zero_budget() -> None:
    config = _providers_config(maximum_per_run=0)
    status = check_budget(estimated_credits=0.0, spent_this_run=0.0, providers_config=config)
    assert status.allowed is True


def test_require_budget_raises_when_projected_spend_exceeds_limit() -> None:
    config = _providers_config(maximum_per_run=10)
    with pytest.raises(CreditBudgetExceededError):
        require_budget(estimated_credits=5.0, spent_this_run=8.0, providers_config=config)


def test_budget_cannot_be_bypassed_by_prior_spend_underreporting() -> None:
    """Even if `spent_this_run` were accidentally passed as 0, a single
    operation whose own cost exceeds the budget must still be refused."""
    config = _providers_config(maximum_per_run=10)
    status = check_budget(estimated_credits=15.0, spent_this_run=0.0, providers_config=config)
    assert status.allowed is False


def test_raising_the_budget_explicitly_allows_the_operation() -> None:
    config = _providers_config(maximum_per_run=50)
    status = check_budget(estimated_credits=15.0, spent_this_run=0.0, providers_config=config)
    assert status.allowed is True
