"""Multi-account round-robin/priority logic for Vibe Prospecting credits.
Spec §6.

`vpai` has no queryable balance or credit-expiry API (see
docs/vibe-credit-strategy.md "What vpai actually reports"), so account
records — including credit expiry — are tracked locally, not fetched from
vpai. Free-trial credits expire 90 days after grant, paid credits 12
months after purchase, and neither rolls over (same doc, "Credit expiry").
Priority ranks by soonest expiry first, not remaining balance, per that
doc's conclusion: a large balance on a near-expiry account is worth less
than it looks, since letting it lapse unused wastes it entirely.

Only one vpai account is authenticated as of this writing (via `vpai
login`'s device-code OAuth flow, not via a tracked email list). This module
is built to work correctly with that single account today — priority
selection trivially returns the only candidate — and extends to the full
4-6-account round-robin spec §6 describes without further changes once
more accounts are configured in `VIBE_ACCOUNT_EMAILS`.
"""

from __future__ import annotations

from datetime import date, timedelta
from enum import StrEnum

from pydantic import BaseModel

FREE_TRIAL_EXPIRY_DAYS = 90
# Spec/user-supplied figure is "12 months"; approximated as 365 days rather
# than calendar-month arithmetic (no rollover either way makes the
# leap-year-scale imprecision immaterial for a credit-expiry deadline).
PAID_CREDIT_EXPIRY_DAYS = 365


class VibeAccountType(StrEnum):
    FREE_TRIAL = "free_trial"
    PAID = "paid"


class VibeAccount(BaseModel):
    """A locally-tracked record of one Vibe Prospecting account.

    vpai itself exposes no account/balance/expiry API, so every field here
    is maintained by hand (or by whatever process records the account's
    signup/purchase date) — never fetched from the CLI.
    """

    identifier: str  # email, or any stable label if no email is tracked
    account_type: VibeAccountType = VibeAccountType.FREE_TRIAL
    credits_granted_at: date | None = None  # None = expiry unknown
    exhausted: bool = False  # set True once known to be spent/rate-limited
    notes: str = ""

    def credits_expire_at(self) -> date | None:
        if self.credits_granted_at is None:
            return None
        days = (
            FREE_TRIAL_EXPIRY_DAYS
            if self.account_type is VibeAccountType.FREE_TRIAL
            else PAID_CREDIT_EXPIRY_DAYS
        )
        return self.credits_granted_at + timedelta(days=days)

    def is_expired(self, today: date | None = None) -> bool:
        expiry = self.credits_expire_at()
        if expiry is None:
            return False  # unknown expiry is never treated as already-expired
        return (today or date.today()) > expiry


def select_next_account(
    accounts: list[VibeAccount], today: date | None = None
) -> VibeAccount | None:
    """Pick the account to spend from next: soonest-expiring first among
    non-expired, non-exhausted accounts.

    Accounts with unknown expiry (`credits_granted_at` unset) sort as if
    expiring immediately (`date.min`) — the conservative choice: spend
    down credits we have no expiry record for before they might lapse
    unrecorded, rather than hoarding an account whose runway we can't
    actually verify. Ties (including "all unknown") break on `identifier`
    for determinism.

    Returns `None` if every configured account is expired or exhausted —
    callers should then fall back to the configured paid `credit_budget`
    (spec §6), which will in turn refuse spend by default (budget = 0)
    unless a human has explicitly raised it.
    """
    today = today or date.today()
    candidates = [a for a in accounts if not a.exhausted and not a.is_expired(today)]
    if not candidates:
        return None

    def sort_key(account: VibeAccount) -> tuple[date, str]:
        return (account.credits_expire_at() or date.min, account.identifier)

    return min(candidates, key=sort_key)


def load_configured_accounts(vibe_account_emails: str | None = None) -> list[VibeAccount]:
    """Build account records from `VIBE_ACCOUNT_EMAILS` (.env, spec §6) — a
    comma-separated list of emails.

    That single env var carries no per-account type or grant-date metadata
    (email addresses are PII and were deliberately kept out of any
    committed config — see config/providers.yaml), so every account loaded
    this way defaults to unknown expiry (`credits_granted_at=None`) until
    the user records real grant dates directly on a `VibeAccount`.

    With zero configured emails — the current state, since only one vpai
    session is authenticated via `vpai login` rather than a tracked email
    list — this returns a single placeholder account so priority selection
    still works correctly for the one real account in use today.
    """
    if not vibe_account_emails or not vibe_account_emails.strip():
        return [VibeAccount(identifier="default")]

    emails = [e.strip() for e in vibe_account_emails.split(",") if e.strip()]
    if not emails:
        return [VibeAccount(identifier="default")]
    return [VibeAccount(identifier=email) for email in emails]
