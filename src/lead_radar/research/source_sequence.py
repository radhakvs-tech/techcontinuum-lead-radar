"""Spec §7 suggested source sequence: company homepage -> AI/product pages
-> changelog -> careers page -> current job descriptions -> engineering
blog -> trust/security page -> press releases -> public GitHub presence.

Providers order their `search()` results by this sequence so a capped
research run (spec §7 "maximum pages per domain") spends its budget on the
highest-value pages first rather than an arbitrary order.
"""

from __future__ import annotations

from lead_radar.models.enums import EvidenceSourceType

ROLE_HOMEPAGE = "homepage"
ROLE_AI_PRODUCT_PAGES = "ai_product_pages"
ROLE_CHANGELOG = "changelog"
ROLE_CAREERS_PAGE = "careers_page"
ROLE_JOB_DESCRIPTIONS = "job_descriptions"
ROLE_ENGINEERING_BLOG = "engineering_blog"
ROLE_TRUST_SECURITY_PAGE = "trust_security_page"
ROLE_PRESS_RELEASES = "press_releases"
ROLE_GITHUB = "github"

SOURCE_SEQUENCE: list[str] = [
    ROLE_HOMEPAGE,
    ROLE_AI_PRODUCT_PAGES,
    ROLE_CHANGELOG,
    ROLE_CAREERS_PAGE,
    ROLE_JOB_DESCRIPTIONS,
    ROLE_ENGINEERING_BLOG,
    ROLE_TRUST_SECURITY_PAGE,
    ROLE_PRESS_RELEASES,
    ROLE_GITHUB,
]

ROLE_SOURCE_TYPES: dict[str, EvidenceSourceType] = {
    ROLE_HOMEPAGE: EvidenceSourceType.COMPANY_WEBSITE,
    ROLE_AI_PRODUCT_PAGES: EvidenceSourceType.PRODUCT_PAGE,
    ROLE_CHANGELOG: EvidenceSourceType.CHANGELOG,
    ROLE_CAREERS_PAGE: EvidenceSourceType.CAREERS_PAGE,
    ROLE_JOB_DESCRIPTIONS: EvidenceSourceType.JOB_DESCRIPTION,
    ROLE_ENGINEERING_BLOG: EvidenceSourceType.ENGINEERING_BLOG,
    ROLE_TRUST_SECURITY_PAGE: EvidenceSourceType.TRUST_CENTRE,
    ROLE_PRESS_RELEASES: EvidenceSourceType.PRESS_RELEASE,
    ROLE_GITHUB: EvidenceSourceType.GITHUB,
}


def ordered_roles() -> list[str]:
    return list(SOURCE_SEQUENCE)
