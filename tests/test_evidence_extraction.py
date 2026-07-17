"""Structural, keyword-based evidence extraction. Spec §5, §7, §20 (Phase 3a).

No real HTML is fetched here — every fixture is synthetic markup for a
fictional company, matching the "no real company names" convention used
elsewhere in this repo's fixtures (spec §19).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from lead_radar.models.enums import EvidenceClassification, EvidenceSourceType
from lead_radar.research.evidence_extraction import (
    extract_public_evidence,
    parse_structure,
    resolve_page_date,
)
from lead_radar.research.models import FetchedPage
from lead_radar.settings import YamlConfig

_KEYWORDS_CONFIG = YamlConfig(
    data={
        "signal_keywords": {
            "platform_or_sre_hiring": ["site reliability engineer", "platform engineer"],
            "action_taking_agent": ["autonomous agent", "acts on your behalf"],
            "ai_beta_to_ga": ["now generally available"],
        },
        "generic_marketing_phrases": ["ai-powered", "cutting-edge ai"],
        "hedge_phrases": ["we are exploring", "considering whether"],
        "observed_fact_source_types": [
            "changelog",
            "careers_page",
            "job_description",
            "press_release",
            "trust_centre",
            "github",
        ],
    }
)


def _page(url: str, html: str, fetched_at: datetime | None = None) -> FetchedPage:
    return FetchedPage(
        url=url,
        final_url=url,
        status_code=200,
        content_type="text/html",
        html=html,
        fetched_at=fetched_at or datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
    )


def test_parse_structure_extracts_title_headings_and_blocks() -> None:
    html = """
    <html><head><title>  Acme Careers  </title></head>
    <body>
      <h1>Open Roles</h1>
      <p>We are hiring a Site Reliability Engineer to scale our platform.</p>
      <h2>Engineering</h2>
      <p>Join our engineering team.</p>
    </body></html>
    """
    structure = parse_structure(html)
    assert structure.title == "Acme Careers"
    assert structure.blocks == [
        ("Open Roles", "We are hiring a Site Reliability Engineer to scale our platform."),
        ("Engineering", "Join our engineering team."),
    ]


def test_resolve_page_date_prefers_meta_published_time() -> None:
    html = """
    <html><head>
      <meta property="article:published_time" content="2026-06-01T00:00:00Z">
    </head><body><time datetime="2026-05-01">May 1</time></body></html>
    """
    structure = parse_structure(html)
    assert resolve_page_date(structure) == date(2026, 6, 1)


def test_resolve_page_date_falls_back_to_time_tag() -> None:
    html = '<html><body><time datetime="2026-05-01">May 1, 2026</time></body></html>'
    structure = parse_structure(html)
    assert resolve_page_date(structure) == date(2026, 5, 1)


def test_resolve_page_date_none_when_no_date_present() -> None:
    html = "<html><body><p>No dates here.</p></body></html>"
    structure = parse_structure(html)
    assert resolve_page_date(structure) is None


def test_careers_page_hiring_keyword_is_observed_fact() -> None:
    html = (
        "<html><body><h1>Careers</h1>"
        "<p>We need a Site Reliability Engineer now.</p></body></html>"
    )
    page = _page("https://acme.example/careers", html)

    evidence = extract_public_evidence(
        1, page, EvidenceSourceType.CAREERS_PAGE, keywords_config=_KEYWORDS_CONFIG
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.signal_type == "platform_or_sre_hiring"
    assert row.classification == EvidenceClassification.OBSERVED_FACT
    assert row.source_type == EvidenceSourceType.CAREERS_PAGE
    assert row.account_id == 1
    assert row.source_url == "https://acme.example/careers"
    assert row.confidence == 0.75


def test_homepage_marketing_copy_is_reasonable_inference_not_observed_fact() -> None:
    """Same phrase, different source_type: a homepage paragraph describing
    the same fact secondhand isn't the primary record of it (spec §5
    preferred-sources hierarchy)."""
    html = "<html><body><p>Our platform engineer team keeps things running.</p></body></html>"
    page = _page("https://acme.example/", html)

    evidence = extract_public_evidence(
        1, page, EvidenceSourceType.COMPANY_WEBSITE, keywords_config=_KEYWORDS_CONFIG
    )

    assert len(evidence) == 1
    assert evidence[0].classification == EvidenceClassification.REASONABLE_INFERENCE
    assert evidence[0].confidence == 0.55


def test_generic_ai_marketing_phrase_alone_is_general_industry_consideration() -> None:
    """Spec §5: 'the conclusion is not based only on marketing phrases such
    as AI-powered.' A bare marketing phrase must never reach OBSERVED_FACT
    or REASONABLE_INFERENCE, even on an otherwise-authoritative page."""
    html = "<html><body><p>Our AI-powered platform delights customers.</p></body></html>"
    page = _page("https://acme.example/changelog", html)

    evidence = extract_public_evidence(
        1, page, EvidenceSourceType.CHANGELOG, keywords_config=_KEYWORDS_CONFIG
    )

    assert len(evidence) == 1
    assert evidence[0].signal_type == "generic_ai_marketing_only"
    assert evidence[0].classification == EvidenceClassification.GENERAL_INDUSTRY_CONSIDERATION
    assert evidence[0].confidence == 0.3


def test_specific_signal_takes_priority_over_generic_marketing_in_same_block() -> None:
    html = (
        "<html><body><p>Our AI-powered agent acts on your behalf across every campaign."
        "</p></body></html>"
    )
    page = _page("https://acme.example/product/agent", html)

    evidence = extract_public_evidence(
        1, page, EvidenceSourceType.PRODUCT_PAGE, keywords_config=_KEYWORDS_CONFIG
    )

    assert len(evidence) == 1
    assert evidence[0].signal_type == "action_taking_agent"


def test_hedged_language_downgrades_to_unknown_requiring_validation() -> None:
    """Even on an authoritative source_type, aspirational language must not
    read as a firm commitment (spec §16 disclaimer principle applied to
    Phase 3a's own structural rules)."""
    html = (
        "<html><body><p>We are exploring whether to launch an autonomous agent next year."
        "</p></body></html>"
    )
    page = _page("https://acme.example/press/roadmap", html)

    evidence = extract_public_evidence(
        1, page, EvidenceSourceType.PRESS_RELEASE, keywords_config=_KEYWORDS_CONFIG
    )

    assert len(evidence) == 1
    assert evidence[0].classification == EvidenceClassification.UNKNOWN_REQUIRING_VALIDATION
    assert evidence[0].confidence == 0.35


def test_no_keyword_match_produces_no_evidence() -> None:
    html = "<html><body><p>We sell garden furniture and outdoor decor.</p></body></html>"
    page = _page("https://acme.example/", html)

    evidence = extract_public_evidence(
        1, page, EvidenceSourceType.COMPANY_WEBSITE, keywords_config=_KEYWORDS_CONFIG
    )

    assert evidence == []


def test_two_matches_on_same_page_share_one_independence_group() -> None:
    """Spec §5: two signals from the same document do not count as
    independent corroboration."""
    html = (
        "<html><body>"
        "<p>We are hiring a Platform Engineer immediately.</p>"
        "<p>Our new release is now generally available to all customers.</p>"
        "</body></html>"
    )
    page = _page("https://acme.example/changelog", html)

    evidence = extract_public_evidence(
        1, page, EvidenceSourceType.CHANGELOG, keywords_config=_KEYWORDS_CONFIG
    )

    assert len(evidence) == 2
    assert evidence[0].independence_group == evidence[1].independence_group


def test_evidence_text_and_summary_are_populated_and_bounded() -> None:
    html = "<html><body><h1>Engineering Blog</h1><p>%s</p></body></html>" % (
        "Autonomous agent details. " * 200
    )
    page = _page("https://acme.example/blog/agent", html)

    evidence = extract_public_evidence(
        1, page, EvidenceSourceType.ENGINEERING_BLOG, keywords_config=_KEYWORDS_CONFIG
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.evidence_summary == "Engineering Blog"
    assert len(row.evidence_text) <= 2000
    assert row.evidence_text  # non-empty
    assert row.published_date is None  # no date anywhere on this page
