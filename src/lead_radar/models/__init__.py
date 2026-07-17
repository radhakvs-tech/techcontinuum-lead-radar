"""Core SQLModel entities. Importing this module registers all tables on
SQLModel.metadata, which db.py relies on for init-db / create_all."""

from lead_radar.models.account import Account, AccountAlias, CompanyMetric
from lead_radar.models.contact import Contact
from lead_radar.models.enums import (
    AccountStatus,
    ARRConfidence,
    Classification,
    ContactRoleCategory,
    EmailVerificationStatus,
    EvidenceClassification,
    EvidenceSourceType,
    OfferCode,
    ReviewerLabel,
)
from lead_radar.models.evidence import Evidence, Signal
from lead_radar.models.offer import OfferRecommendation
from lead_radar.models.provider_usage import ProviderUsage
from lead_radar.models.research import ResearchRun
from lead_radar.models.review import HumanReview
from lead_radar.models.scoring import ScoreContribution, ScoreRun

__all__ = [
    "ARRConfidence",
    "Account",
    "AccountAlias",
    "AccountStatus",
    "Classification",
    "CompanyMetric",
    "Contact",
    "ContactRoleCategory",
    "EmailVerificationStatus",
    "Evidence",
    "EvidenceClassification",
    "EvidenceSourceType",
    "HumanReview",
    "OfferCode",
    "OfferRecommendation",
    "ProviderUsage",
    "ResearchRun",
    "ReviewerLabel",
    "ScoreContribution",
    "ScoreRun",
    "Signal",
]
