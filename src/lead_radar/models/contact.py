"""Contact entity. Spec §11 (contact discovery — gated by human approval).

No functionality in this module retrieves contacts; that is Phase 4. This
table exists now because it is part of the core data model (spec §12), and
review/guardrails.py needs AccountStatus to reason about eligibility before
any fetching code exists.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlmodel import Field, SQLModel

from lead_radar.models.enums import ContactRoleCategory, EmailVerificationStatus


class Contact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True)

    name: str
    exact_title: str
    role_category: ContactRoleCategory
    public_profile_url: str | None = None
    reason_selected: str
    role_change_date: date | None = None

    email: str | None = None
    email_verification_status: EmailVerificationStatus = EmailVerificationStatus.NOT_RETRIEVED
    email_retrieved_at: datetime | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
