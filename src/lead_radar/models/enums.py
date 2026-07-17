"""Shared enumerations for the Lead Radar data model. Spec §5, §10, §11, §12."""

from __future__ import annotations

from enum import StrEnum


class ARRConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class EvidenceSourceType(StrEnum):
    COMPANY_WEBSITE = "company_website"
    PRODUCT_PAGE = "product_page"
    PRODUCT_DOCUMENTATION = "product_documentation"
    CHANGELOG = "changelog"
    CAREERS_PAGE = "careers_page"
    JOB_DESCRIPTION = "job_description"
    ENGINEERING_BLOG = "engineering_blog"
    GITHUB = "github"
    TRUST_CENTRE = "trust_centre"
    PRESS_RELEASE = "press_release"
    FUNDING_ANNOUNCEMENT = "funding_announcement"
    CONFERENCE_TALK = "conference_talk"
    COMPANY_SOCIAL_POST = "company_social_post"
    VIBE_BUSINESS_DATA = "vibe_business_data"
    VIBE_EVENT_DATA = "vibe_event_data"
    OTHER_PERMITTED_SOURCE = "other_permitted_source"


class EvidenceClassification(StrEnum):
    OBSERVED_FACT = "OBSERVED_FACT"
    REASONABLE_INFERENCE = "REASONABLE_INFERENCE"
    GENERAL_INDUSTRY_CONSIDERATION = "GENERAL_INDUSTRY_CONSIDERATION"
    UNKNOWN_REQUIRING_VALIDATION = "UNKNOWN_REQUIRING_VALIDATION"


class AccountStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    PRELIMINARY_QUALIFIED = "PRELIMINARY_QUALIFIED"
    RESEARCHED = "RESEARCHED"
    SCORED = "SCORED"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    APPROVED_FOR_CONTACT_DISCOVERY = "APPROVED_FOR_CONTACT_DISCOVERY"
    REJECTED = "REJECTED"
    WATCHLIST = "WATCHLIST"
    CONTACTED = "CONTACTED"
    POSITIVE_REPLY = "POSITIVE_REPLY"
    NEGATIVE_REPLY = "NEGATIVE_REPLY"
    MEETING_BOOKED = "MEETING_BOOKED"


class ReviewerLabel(StrEnum):
    HIGH_PRIORITY = "HIGH_PRIORITY"
    GOOD_FIT_LOW_SIGNAL = "GOOD_FIT_LOW_SIGNAL"
    WRONG_ICP = "WRONG_ICP"
    WEAK_SIGNAL = "WEAK_SIGNAL"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    DUPLICATE = "DUPLICATE"
    NOT_SUITABLE_FOR_SMALL_ADVISORY = "NOT_SUITABLE_FOR_SMALL_ADVISORY"


class Classification(StrEnum):
    HIGH_INTENT = "HIGH_INTENT"
    HIGH_PRIORITY_REVIEW = "HIGH_PRIORITY_REVIEW"
    GOOD_FIT_LOW_SIGNAL = "GOOD_FIT_LOW_SIGNAL"
    WATCHLIST = "WATCHLIST"
    IGNORE_WRONG_ICP = "IGNORE_WRONG_ICP"
    IGNORE_WEAK_SIGNAL = "IGNORE_WEAK_SIGNAL"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class ContactRoleCategory(StrEnum):
    STRATEGIC_BUYER = "strategic_buyer"
    TECHNICAL_CHAMPION = "technical_champion"


class EmailVerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    UNDELIVERABLE = "undeliverable"
    NOT_RETRIEVED = "not_retrieved"


class OfferCode(StrEnum):
    OFFER_A_AGENTIC_MARTECH = "offer_a_agentic_product_readiness_for_martech_saas"
    OFFER_B_AI_PRODUCTION_READINESS = "offer_b_ai_production_readiness_sprint"
    OFFER_C_CLOUD_AI_UNIT_ECONOMICS = "offer_c_cloud_and_ai_unit_economics_sprint"
    OFFER_D_AI_NATIVE_MODERNISATION = "offer_d_ai_native_modernisation_blueprint"
