"""PatternGuessProvider against httpx.MockTransport — zero real network.
Spec §7, §20 Phase 3a.

Mirrors tests/test_manual_url_provider.py's approach: every HTTP call is
intercepted by a handler function, so this validates the real fetch/
validation code path without ever touching the internet.
"""

from __future__ import annotations

import httpx
import pytest

from lead_radar.providers.manual_url_provider import ManualUrlManifest
from lead_radar.providers.pattern_guess_provider import PatternGuessProvider
from lead_radar.research.fetch_governor import FetchGovernor
from lead_radar.research.source_sequence import (
    ROLE_CAREERS_PAGE,
    ROLE_CHANGELOG,
    ROLE_GITHUB,
    ROLE_HOMEPAGE,
)
from lead_radar.settings import YamlConfig


def _config(**overrides: object) -> YamlConfig:
    web_research = {
        "active_provider": "manual_url",
        "max_pages_per_domain": 8,
        "page_fetch_timeout_seconds": 15,
        "max_content_size_bytes": 2_000_000,
        "respect_robots_txt": True,
        "min_seconds_between_requests_per_domain": 0.0,
        "preliminary_score_threshold": 45,
        "user_agent": "TechContinuumLeadRadarBot/0.1-test",
        "manual_url_manifest_path": "data/imports/manual_research_urls.yaml",
    }
    web_research.update(overrides)
    return YamlConfig(data={"web_research": web_research})


def _url_patterns_config() -> YamlConfig:
    return YamlConfig(
        data={
            "role_path_patterns": {
                "homepage": ["/"],
                "changelog": ["/changelog", "/release-notes"],
                "careers_page": ["/careers", "/jobs"],
                "github": [],
            },
            "github_org_slug_variants": ["{label}", "{label}hq"],
        }
    )


def _robots_ok(request: httpx.Request) -> httpx.Response | None:
    if request.url.path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nAllow: /\n")
    return None


def _company_page(title: str, description: str = "") -> httpx.Response:
    return httpx.Response(
        200,
        content=(
            f"<html><head><title>{title}</title>"
            f'<meta name="description" content="{description}"></head>'
            f"<body><p>content</p></body></html>"
        ).encode(),
    )


def test_first_matching_pattern_is_accepted_and_stops_trying_more() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        robots = _robots_ok(request)
        if robots is not None:
            return robots
        if request.url.path == "/careers":
            return _company_page("Careers at Acme")
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = PatternGuessProvider(
        {"acme.example": "Acme"},
        http_client=client,
        providers_config=_config(),
        url_patterns_config=_url_patterns_config(),
    )

    results = provider.search("acme.example", roles=[ROLE_CAREERS_PAGE])

    assert len(results) == 1
    assert results[0].url == "https://acme.example/careers"
    assert results[0].source_role == ROLE_CAREERS_PAGE
    # /jobs (the second careers_page pattern) must never have been tried
    # once /careers already matched.
    assert "/jobs" not in calls


def test_wrong_company_match_is_rejected_and_next_pattern_is_tried() -> None:
    """This is the GoZen scenario from the real validation session: a 200
    response from the wrong company must not be accepted."""

    def handler(request: httpx.Request) -> httpx.Response:
        robots = _robots_ok(request)
        if robots is not None:
            return robots
        if request.url.path == "/careers":
            return _company_page("Careers at Wrong Company Inc")
        if request.url.path == "/jobs":
            return _company_page("Jobs at Acme")
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = PatternGuessProvider(
        {"acme.example": "Acme"},
        http_client=client,
        providers_config=_config(),
        url_patterns_config=_url_patterns_config(),
    )

    results = provider.search("acme.example", roles=[ROLE_CAREERS_PAGE])

    assert len(results) == 1
    assert results[0].url == "https://acme.example/jobs"


def test_no_pattern_hit_falls_back_to_manual_manifest() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        robots = _robots_ok(request)
        if robots is not None:
            return robots
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    manifest: ManualUrlManifest = {
        "acme.example": {ROLE_CAREERS_PAGE: ["https://acme.example/work-with-us"]}
    }
    provider = PatternGuessProvider(
        {"acme.example": "Acme"},
        fallback_manifest=manifest,
        http_client=client,
        providers_config=_config(),
        url_patterns_config=_url_patterns_config(),
    )

    results = provider.search("acme.example", roles=[ROLE_CAREERS_PAGE])

    assert len(results) == 1
    assert results[0].url == "https://acme.example/work-with-us"


def test_no_pattern_hit_and_no_manifest_entry_yields_nothing_for_that_role() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        robots = _robots_ok(request)
        if robots is not None:
            return robots
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = PatternGuessProvider(
        {"acme.example": "Acme"},
        http_client=client,
        providers_config=_config(),
        url_patterns_config=_url_patterns_config(),
    )

    results = provider.search("acme.example", roles=[ROLE_CAREERS_PAGE])
    assert results == []


def test_source_sequence_order_is_preserved_across_guessed_and_fallback_hits() -> None:
    """homepage and careers_page are guessed; changelog only resolves via
    the manual fallback — the returned order must still follow the
    requested role order, not "guessed first, fallback last"."""

    def handler(request: httpx.Request) -> httpx.Response:
        robots = _robots_ok(request)
        if robots is not None:
            return robots
        if request.url.path in ("/", "/careers"):
            return _company_page("Acme")
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    manifest: ManualUrlManifest = {
        "acme.example": {ROLE_CHANGELOG: ["https://acme.example/updates"]}
    }
    provider = PatternGuessProvider(
        {"acme.example": "Acme"},
        fallback_manifest=manifest,
        http_client=client,
        providers_config=_config(),
        url_patterns_config=_url_patterns_config(),
    )

    results = provider.search(
        "acme.example", roles=[ROLE_HOMEPAGE, ROLE_CHANGELOG, ROLE_CAREERS_PAGE]
    )

    assert [r.url for r in results] == [
        "https://acme.example/",
        "https://acme.example/updates",
        "https://acme.example/careers",
    ]


def test_github_org_slug_guessing_tries_variants_in_order() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.host == "github.com":
            if request.url.path == "/acmehq":
                return _company_page("acmehq · GitHub")
            return httpx.Response(404)
        robots = _robots_ok(request)
        if robots is not None:
            return robots
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = PatternGuessProvider(
        {"acme.example": "acme"},
        http_client=client,
        providers_config=_config(),
        url_patterns_config=_url_patterns_config(),
    )

    results = provider.search("acme.example", roles=[ROLE_GITHUB])

    assert len(results) == 1
    assert results[0].url == "https://github.com/acmehq"
    # robots.txt fetched once for github.com, then the two slug variants in
    # order — the first rejected (wrong/no match), the second accepted.
    assert calls == ["/robots.txt", "/acme", "/acmehq"]


def test_fetch_page_reuses_cache_from_search_time_validation() -> None:
    """The real fetch that validated a guessed URL during search() must not
    be repeated when the research pipeline later calls fetch_page() on the
    exact same URL."""
    call_count = {"careers": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        robots = _robots_ok(request)
        if robots is not None:
            return robots
        if request.url.path == "/careers":
            call_count["careers"] += 1
            return _company_page("Careers at Acme")
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = PatternGuessProvider(
        {"acme.example": "Acme"},
        http_client=client,
        providers_config=_config(),
        url_patterns_config=_url_patterns_config(),
    )

    results = provider.search("acme.example", roles=[ROLE_CAREERS_PAGE])
    page = provider.fetch_page(results[0].url)

    assert page.from_cache is True
    assert call_count["careers"] == 1


def test_per_domain_fetch_cap_stops_further_pattern_guessing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        robots = _robots_ok(request)
        if robots is not None:
            return robots
        return httpx.Response(404)  # every guess misses, so all budget goes to guessing

    client = httpx.Client(transport=httpx.MockTransport(handler))
    governor = FetchGovernor(max_pages_per_domain=1, min_seconds_between_requests=0.0)
    provider = PatternGuessProvider(
        {"acme.example": "Acme"},
        governor=governor,
        http_client=client,
        providers_config=_config(),
        url_patterns_config=_url_patterns_config(),
    )

    # changelog has two patterns (/changelog, /release-notes); the cap of 1
    # is consumed by the first miss, so the second pattern is never tried
    # and this role resolves to nothing rather than raising.
    results = provider.search("acme.example", roles=[ROLE_CHANGELOG])
    assert results == []


def test_no_expected_company_name_falls_back_to_domain_label() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        robots = _robots_ok(request)
        if robots is not None:
            return robots
        if request.url.path == "/careers":
            return _company_page("Careers at Acme")
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = PatternGuessProvider(
        {},  # no explicit company name for acme.example
        http_client=client,
        providers_config=_config(),
        url_patterns_config=_url_patterns_config(),
    )

    results = provider.search("acme.example", roles=[ROLE_CAREERS_PAGE])
    assert len(results) == 1


@pytest.mark.parametrize(
    ("title", "expected_name", "should_match"),
    [
        ("Careers at Acme", "Acme", True),
        ("Acme Careers | Join our team", "Acme", True),
        ("Careers at Wrong Company Inc", "Acme", False),
        ("Jobs at Northwind Traders", "Acme", False),
    ],
)
def test_matches_company_heuristic(title: str, expected_name: str, should_match: bool) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        robots = _robots_ok(request)
        if robots is not None:
            return robots
        return _company_page(title)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = PatternGuessProvider(
        {"acme.example": expected_name},
        http_client=client,
        providers_config=_config(),
        url_patterns_config=_url_patterns_config(),
    )
    page = provider.fetch_page("https://acme.example/careers")
    assert provider._matches_company(page, expected_name) is should_match
