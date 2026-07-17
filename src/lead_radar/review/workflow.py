"""Human-review status transitions. Spec §10."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session

from lead_radar.models.account import Account
from lead_radar.models.enums import AccountStatus, ReviewerLabel
from lead_radar.models.review import HumanReview


def apply_review_decision(
    session: Session,
    account: Account,
    reviewer: str,
    new_status: AccountStatus,
    reason: str,
    reviewer_label: ReviewerLabel | None = None,
    scoring_version: str | None = None,
) -> HumanReview:
    old_status = account.status
    account.status = new_status
    account.updated_at = datetime.now(UTC)

    review = HumanReview(
        account_id=account.id,
        reviewer=reviewer,
        old_status=old_status,
        new_status=new_status,
        reviewer_label=reviewer_label,
        reason=reason,
        scoring_version=scoring_version,
    )
    session.add(account)
    session.add(review)
    session.commit()
    session.refresh(review)
    return review
