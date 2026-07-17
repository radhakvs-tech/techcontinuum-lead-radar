"""Spec §11, §23. Acceptance #10, #11, #12."""

from __future__ import annotations

import pytest

from lead_radar.models.enums import AccountStatus
from lead_radar.review.guardrails import (
    ContactDiscoveryNotApprovedError,
    EmailEnrichmentNotApprovedError,
    PhoneRetrievalDisabledError,
    can_discover_contacts,
    can_enrich_email,
    guard_phone_retrieval_call,
    require_contact_discovery_approved,
    require_email_enrichment_approved,
)


@pytest.mark.parametrize(
    "status",
    [
        AccountStatus.DISCOVERED,
        AccountStatus.PRELIMINARY_QUALIFIED,
        AccountStatus.SCORED,
        AccountStatus.PENDING_HUMAN_REVIEW,
        AccountStatus.REJECTED,
        AccountStatus.WATCHLIST,
    ],
)
def test_contact_discovery_blocked_before_approval(status: AccountStatus) -> None:
    assert can_discover_contacts(status) is False
    with pytest.raises(ContactDiscoveryNotApprovedError):
        require_contact_discovery_approved(status)


def test_contact_discovery_allowed_after_approval() -> None:
    assert can_discover_contacts(AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY) is True
    require_contact_discovery_approved(AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY)  # no raise


def test_email_enrichment_blocked_without_second_approval() -> None:
    status = AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY
    assert can_enrich_email(status, email_enrichment_approved=False) is False
    with pytest.raises(EmailEnrichmentNotApprovedError):
        require_email_enrichment_approved(status, email_enrichment_approved=False)


def test_email_enrichment_blocked_even_if_approved_flag_true_but_account_not_approved() -> None:
    status = AccountStatus.PENDING_HUMAN_REVIEW
    assert can_enrich_email(status, email_enrichment_approved=True) is False


def test_email_enrichment_allowed_with_both_approvals() -> None:
    status = AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY
    assert can_enrich_email(status, email_enrichment_approved=True) is True
    require_email_enrichment_approved(status, email_enrichment_approved=True)  # no raise


def test_phone_retrieval_is_permanently_disabled() -> None:
    with pytest.raises(PhoneRetrievalDisabledError):
        guard_phone_retrieval_call()
