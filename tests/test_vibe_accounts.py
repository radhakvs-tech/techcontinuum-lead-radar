"""Spec §6 multi-account round-robin. vpai has no balance/expiry API, so
account expiry is tracked locally — priority ranks by soonest expiry, not
remaining balance (docs/vibe-credit-strategy.md 'Credit expiry')."""

from __future__ import annotations

from datetime import date, timedelta

from lead_radar.providers.vibe_accounts import (
    VibeAccount,
    VibeAccountType,
    load_configured_accounts,
    select_next_account,
)

TODAY = date(2026, 7, 17)


def test_free_trial_expires_90_days_after_grant() -> None:
    account = VibeAccount(
        identifier="a@example.com",
        account_type=VibeAccountType.FREE_TRIAL,
        credits_granted_at=date(2026, 1, 1),
    )
    assert account.credits_expire_at() == date(2026, 4, 1)


def test_paid_credits_expire_365_days_after_grant() -> None:
    account = VibeAccount(
        identifier="a@example.com",
        account_type=VibeAccountType.PAID,
        credits_granted_at=date(2026, 1, 1),
    )
    assert account.credits_expire_at() == date(2027, 1, 1)


def test_unknown_grant_date_means_unknown_expiry_and_never_expired() -> None:
    account = VibeAccount(identifier="a@example.com")
    assert account.credits_expire_at() is None
    assert account.is_expired(TODAY) is False


def test_single_account_is_trivially_selected() -> None:
    accounts = [VibeAccount(identifier="only@example.com")]
    assert select_next_account(accounts, today=TODAY) is accounts[0]


def test_selects_soonest_expiring_account_first_not_largest_balance() -> None:
    soon_to_expire = VibeAccount(
        identifier="soon@example.com",
        account_type=VibeAccountType.FREE_TRIAL,
        credits_granted_at=TODAY - timedelta(days=85),  # expires in 5 days
    )
    plenty_of_runway = VibeAccount(
        identifier="later@example.com",
        account_type=VibeAccountType.PAID,
        credits_granted_at=TODAY,  # expires in 365 days
    )
    selected = select_next_account([plenty_of_runway, soon_to_expire], today=TODAY)
    assert selected is soon_to_expire


def test_unknown_expiry_account_is_treated_as_expiring_soonest() -> None:
    unknown_expiry = VibeAccount(identifier="unknown@example.com")
    known_runway = VibeAccount(
        identifier="known@example.com",
        account_type=VibeAccountType.PAID,
        credits_granted_at=TODAY,
    )
    selected = select_next_account([known_runway, unknown_expiry], today=TODAY)
    assert selected is unknown_expiry


def test_expired_accounts_are_excluded() -> None:
    expired = VibeAccount(
        identifier="expired@example.com",
        account_type=VibeAccountType.FREE_TRIAL,
        credits_granted_at=TODAY - timedelta(days=200),
    )
    still_valid = VibeAccount(
        identifier="valid@example.com",
        account_type=VibeAccountType.FREE_TRIAL,
        credits_granted_at=TODAY,
    )
    selected = select_next_account([expired, still_valid], today=TODAY)
    assert selected is still_valid


def test_exhausted_accounts_are_excluded() -> None:
    exhausted = VibeAccount(identifier="exhausted@example.com", exhausted=True)
    fresh = VibeAccount(identifier="fresh@example.com")
    selected = select_next_account([exhausted, fresh], today=TODAY)
    assert selected is fresh


def test_returns_none_when_every_account_is_expired_or_exhausted() -> None:
    expired = VibeAccount(
        identifier="expired@example.com",
        credits_granted_at=TODAY - timedelta(days=200),
    )
    exhausted = VibeAccount(identifier="exhausted@example.com", exhausted=True)
    assert select_next_account([expired, exhausted], today=TODAY) is None


def test_load_configured_accounts_falls_back_to_single_default_when_no_emails_set() -> None:
    accounts = load_configured_accounts(None)
    assert len(accounts) == 1
    assert accounts[0].identifier == "default"


def test_load_configured_accounts_parses_comma_separated_emails() -> None:
    accounts = load_configured_accounts("a@example.com, b@example.com,c@example.com")
    assert [a.identifier for a in accounts] == ["a@example.com", "b@example.com", "c@example.com"]
