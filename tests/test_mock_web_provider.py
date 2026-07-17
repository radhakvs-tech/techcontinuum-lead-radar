"""MockWebProvider — offline WebResearchProvider. Spec §7. Everything here
runs with zero network access, per this session's instruction to validate
the whole pipeline against mocks before any real fetch."""

from __future__ import annotations

import pytest

from lead_radar.models.enums import EvidenceSourceType
from lead_radar.providers.mock_web_provider import (
    FixturePage,
    MockWebProvider,
    MockWebProviderFixtures,
)
from lead_radar.research.fetch_governor import FetchGovernor
from lead_radar.research.models import (
    FetchCapExceededError,
    PageFetchError,
    RobotsDisallowedError,
    SearchResult,
)
from lead_radar.research.source_sequence import (
    ROLE_CAREERS_PAGE,
    ROLE_CHANGELOG,
    ROLE_HOMEPAGE,
)
from lead_radar.settings import YamlConfig

_CONFIG = YamlConfig(
    data={
        "web_research": {
            "active_provider": "mock",
            "max_pages_per_domain": 8,
            "page_fetch_timeout_seconds": 15,
            "max_content_size_bytes": 2_000_000,
            "respect_robots_txt": True,
            "min_seconds_between_requests_per_domain": 0.0,
            "preliminary_score_threshold": 45,
            "user_agent": "TestBot/1.0",
            "manual_url_manifest_path": "data/imports/manual_research_urls.yaml",
        }
    }
)


def test_search_orders_results_by_source_sequence_not_insertion_order() -> None:
    fixtures = MockWebProviderFixtures(
        search_results={
            "acme.example": [
                SearchResult(
                    url="https://acme.example/careers",
                    source_role=ROLE_CAREERS_PAGE,
                    source_type=EvidenceSourceType.CAREERS_PAGE,
                ),
                SearchResult(
                    url="https://acme.example/",
                    source_role=ROLE_HOMEPAGE,
                    source_type=EvidenceSourceType.COMPANY_WEBSITE,
                ),
                SearchResult(
                    url="https://acme.example/changelog",
                    source_role=ROLE_CHANGELOG,
                    source_type=EvidenceSourceType.CHANGELOG,
                ),
            ]
        }
    )
    provider = MockWebProvider(fixtures, providers_config=_CONFIG)

    results = provider.search("acme.example")

    assert [r.url for r in results] == [
        "https://acme.example/",
        "https://acme.example/changelog",
        "https://acme.example/careers",
    ]


def test_search_filters_to_requested_roles() -> None:
    fixtures = MockWebProviderFixtures(
        search_results={
            "acme.example": [
                SearchResult(
                    url="https://acme.example/careers",
                    source_role=ROLE_CAREERS_PAGE,
                    source_type=EvidenceSourceType.CAREERS_PAGE,
                ),
                SearchResult(
                    url="https://acme.example/",
                    source_role=ROLE_HOMEPAGE,
                    source_type=EvidenceSourceType.COMPANY_WEBSITE,
                ),
            ]
        }
    )
    provider = MockWebProvider(fixtures, providers_config=_CONFIG)

    results = provider.search("acme.example", roles=[ROLE_CAREERS_PAGE])

    assert [r.url for r in results] == ["https://acme.example/careers"]


def test_fetch_page_returns_fixture_html() -> None:
    url = "https://acme.example/"
    fixtures = MockWebProviderFixtures(pages={url: FixturePage(html="<html>hi</html>")})
    provider = MockWebProvider(fixtures, providers_config=_CONFIG)

    page = provider.fetch_page(url)

    assert page.html == "<html>hi</html>"
    assert page.status_code == 200
    assert page.from_cache is False


def test_fetch_page_raises_when_no_fixture_registered() -> None:
    provider = MockWebProvider(MockWebProviderFixtures(), providers_config=_CONFIG)
    with pytest.raises(PageFetchError):
        provider.fetch_page("https://acme.example/missing")


def test_second_fetch_of_same_url_is_served_from_cache() -> None:
    url = "https://acme.example/"
    governor = FetchGovernor(max_pages_per_domain=1, min_seconds_between_requests=0.0)
    fixtures = MockWebProviderFixtures(pages={url: FixturePage(html="<html>hi</html>")})
    provider = MockWebProvider(fixtures, governor=governor, providers_config=_CONFIG)

    first = provider.fetch_page(url)
    second = provider.fetch_page(url)

    assert first.from_cache is False
    assert second.from_cache is True


def test_per_domain_cap_blocks_a_second_distinct_page() -> None:
    governor = FetchGovernor(max_pages_per_domain=1, min_seconds_between_requests=0.0)
    fixtures = MockWebProviderFixtures(
        pages={
            "https://acme.example/a": FixturePage(html="<html>a</html>"),
            "https://acme.example/b": FixturePage(html="<html>b</html>"),
        }
    )
    provider = MockWebProvider(fixtures, governor=governor, providers_config=_CONFIG)

    provider.fetch_page("https://acme.example/a")
    with pytest.raises(FetchCapExceededError):
        provider.fetch_page("https://acme.example/b")


def test_cache_hit_does_not_consume_domain_cap() -> None:
    """A cached page is served without touching the per-domain fetch
    budget — spec §7 lists the cache and the page cap as distinct controls."""
    governor = FetchGovernor(max_pages_per_domain=1, min_seconds_between_requests=0.0)
    url = "https://acme.example/"
    fixtures = MockWebProviderFixtures(pages={url: FixturePage(html="<html>hi</html>")})
    provider = MockWebProvider(fixtures, governor=governor, providers_config=_CONFIG)

    provider.fetch_page(url)
    provider.fetch_page(url)  # cache hit, must not raise FetchCapExceededError
    provider.fetch_page(url)


def test_robots_disallow_blocks_fetch() -> None:
    url = "https://acme.example/careers"
    fixtures = MockWebProviderFixtures(
        pages={url: FixturePage(html="<html>careers</html>")},
        robots_txt={"https://acme.example": "User-agent: *\nDisallow: /careers\n"},
    )
    provider = MockWebProvider(fixtures, providers_config=_CONFIG)

    with pytest.raises(RobotsDisallowedError):
        provider.fetch_page(url)


def test_respect_robots_txt_false_bypasses_robots_check() -> None:
    url = "https://acme.example/careers"
    fixtures = MockWebProviderFixtures(
        pages={url: FixturePage(html="<html>careers</html>")},
        robots_txt={"https://acme.example": "User-agent: *\nDisallow: /careers\n"},
    )
    provider = MockWebProvider(fixtures, respect_robots_txt=False, providers_config=_CONFIG)

    page = provider.fetch_page(url)
    assert page.html == "<html>careers</html>"


def test_rate_limit_throttles_second_fetch_to_same_domain() -> None:
    sleeps: list[float] = []
    # record_fetch("a") -> 0.0, throttle("b") -> 0.5, record_fetch("b") -> 0.5
    clock_values = iter([0.0, 0.5, 0.5])
    governor = FetchGovernor(
        max_pages_per_domain=8,
        min_seconds_between_requests=2.0,
        clock=lambda: next(clock_values),
        sleep=sleeps.append,
    )
    fixtures = MockWebProviderFixtures(
        pages={
            "https://acme.example/a": FixturePage(html="<html>a</html>"),
            "https://acme.example/b": FixturePage(html="<html>b</html>"),
        }
    )
    provider = MockWebProvider(fixtures, governor=governor, providers_config=_CONFIG)

    provider.fetch_page("https://acme.example/a")
    provider.fetch_page("https://acme.example/b")

    assert sleeps == [1.5]
