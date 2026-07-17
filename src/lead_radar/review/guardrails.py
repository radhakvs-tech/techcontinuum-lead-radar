"""Contact and email enrichment guardrails. Spec §11, §23, acceptance
criteria #10-12.

These are pure, dependency-free checks so they can guard a future Phase 4
contact-fetching call site without that code existing yet. Phone retrieval
is not config-driven at all — it is a hard constant denial, because spec
§23 lists it as a constraint that must never be violated regardless of
configuration.
"""

from __future__ import annotations

from lead_radar.models.enums import AccountStatus

PHONE_RETRIEVAL_ENABLED = False


class GuardrailViolation(Exception):
    """Raised when code attempts an action a human approval gate forbids."""


class ContactDiscoveryNotApprovedError(GuardrailViolation):
    pass


class EmailEnrichmentNotApprovedError(GuardrailViolation):
    pass


class PhoneRetrievalDisabledError(GuardrailViolation):
    pass


def can_discover_contacts(account_status: AccountStatus) -> bool:
    """No company may move directly from discovery to contact enrichment (spec §10)."""
    return account_status == AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY


def can_enrich_email(account_status: AccountStatus, email_enrichment_approved: bool) -> bool:
    """Email retrieval requires a *second*, separate approval beyond the
    contact-discovery approval (spec §6, §11, §23)."""
    return can_discover_contacts(account_status) and email_enrichment_approved


def require_contact_discovery_approved(account_status: AccountStatus) -> None:
    if not can_discover_contacts(account_status):
        raise ContactDiscoveryNotApprovedError(
            f"Contact discovery requires status={AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY!r}, "
            f"got {account_status!r}."
        )


def require_email_enrichment_approved(
    account_status: AccountStatus, email_enrichment_approved: bool
) -> None:
    require_contact_discovery_approved(account_status)
    if not email_enrichment_approved:
        raise EmailEnrichmentNotApprovedError(
            "Email enrichment requires a separate, explicit second approval."
        )


def guard_phone_retrieval_call() -> None:
    """Call at the top of any phone-retrieval code path. Always raises: phone
    retrieval is a hard constant denial, not a configurable option."""
    assert not PHONE_RETRIEVAL_ENABLED  # pragma: no cover - must never become True
    raise PhoneRetrievalDisabledError("Phone number retrieval is permanently disabled (spec §23).")
