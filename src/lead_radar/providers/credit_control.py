"""Vibe credit budget enforcement. Spec §6.

The real Vibe connector doesn't exist until Phase 2, but the budget model
is defined now so it can't be accidentally bypassed later: any code path
that will eventually spend credits must go through `check_budget` first.
Budgets default to zero (config/providers.yaml `credit_budget:`), so credit
spend is refused unless a human has explicitly raised the limit.
"""

from __future__ import annotations

from pydantic import BaseModel

from lead_radar.settings import YamlConfig, get_providers_config


class CreditBudgetExceededError(Exception):
    pass


class CreditBudgetStatus(BaseModel):
    allowed: bool
    estimated_credits: float
    maximum_per_run: float
    spent_this_run: float
    reason: str


def check_budget(
    estimated_credits: float,
    spent_this_run: float,
    providers_config: YamlConfig | None = None,
) -> CreditBudgetStatus:
    config = providers_config or get_providers_config()
    budget = config["credit_budget"]
    maximum_per_run = float(budget["maximum_per_run"])

    projected = spent_this_run + estimated_credits
    if projected > maximum_per_run:
        return CreditBudgetStatus(
            allowed=False,
            estimated_credits=estimated_credits,
            maximum_per_run=maximum_per_run,
            spent_this_run=spent_this_run,
            reason=(
                f"projected spend {projected:.2f} credits would exceed maximum_per_run "
                f"{maximum_per_run:.2f}. Raise config/providers.yaml credit_budget.maximum_per_run "
                "explicitly to proceed."
            ),
        )
    return CreditBudgetStatus(
        allowed=True,
        estimated_credits=estimated_credits,
        maximum_per_run=maximum_per_run,
        spent_this_run=spent_this_run,
        reason="within budget",
    )


def require_budget(
    estimated_credits: float,
    spent_this_run: float,
    providers_config: YamlConfig | None = None,
) -> CreditBudgetStatus:
    status = check_budget(estimated_credits, spent_this_run, providers_config)
    if not status.allowed:
        raise CreditBudgetExceededError(status.reason)
    return status
