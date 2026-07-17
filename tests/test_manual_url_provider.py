"""ManualUrlProvider against httpx.MockTransport — exercises the real HTTP
fetch code path (timeouts, content-size truncation, robots.txt, per-domain
cap, caching) with zero real network access. No test in this file ever
contacts the internet: `httpx.MockTransport(handler)` intercepts every
request. This mirrors how tests/test_vibe_provider.py exercises
VibeProvider via a FakeVpaiRunner instead of the real `vpai` binary.
"""

from __future__ import annotations

import httpx
import pytest

from lead_radar.providers.manual_url_provider import ManualUrlProvider
from lead_radar.research.fetch_governor import FetchGovernor
from lead_radar.research.models import FetchCapExceededError, PageFetchError, RobotsDisallowedError
from lead_radar.research.source_sequence import ROLE_CAREERS_PAGE, ROLE_HOMEPAGE
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


def test_search_reads_manifest_ordered_by_requested_roles() -> None:
    manifest = {
        "acme.example": {
            ROLE_CAREERS_PAGE: ["https://acme.example/careers"],
            ROLE_HOMEPAGE: ["https://acme.example/"],
        }
    }
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    provider = ManualUrlProvider(manifest, http_client=client, providers_config=_config())

    results = provider.search("acme.example")

    assert [r.url for r in results] == ["https://acme.example/", "https://acme.example/careers"]


def test_search_returns_nothing_for_a_domain_absent_from_the_manifest() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    provider = ManualUrlProvider({}, http_client=client, providers_config=_config())
    assert provider.search("unknown.example") == []


def test_fetch_page_returns_html_and_records_cache() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, content=b"<html><body>hi</body></html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ManualUrlProvider({}, http_client=client, providers_config=_config())

    page = provider.fetch_page("https://acme.example/")
    assert page.html == "<html><body>hi</body></html>"
    assert page.status_code == 200
    assert page.from_cache is False

    cached = provider.fetch_page("https://acme.example/")
    assert cached.from_cache is True
    # robots.txt fetched once, page fetched once — the second fetch_page
    # call must not have hit the network again at all.
    assert calls == ["https://acme.example/robots.txt", "https://acme.example/"]


def test_fetch_page_raises_on_http_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(500, content=b"boom")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ManualUrlProvider({}, http_client=client, providers_config=_config())

    with pytest.raises(PageFetchError):
        provider.fetch_page("https://acme.example/broken")


def test_fetch_page_raises_page_fetch_error_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        raise httpx.ReadTimeout("simulated timeout", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ManualUrlProvider({}, http_client=client, providers_config=_config())

    with pytest.raises(PageFetchError):
        provider.fetch_page("https://acme.example/slow")


def test_fetch_page_truncates_content_over_the_size_limit() -> None:
    big_body = b"<html><body>" + b"x" * 1000 + b"</body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, content=big_body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ManualUrlProvider(
        {}, http_client=client, providers_config=_config(max_content_size_bytes=100)
    )

    page = provider.fetch_page("https://acme.example/huge")
    assert page.truncated is True
    assert len(page.html.encode("utf-8")) <= 100


def test_fetch_page_respects_robots_disallow() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /careers\n")
        return httpx.Response(200, content=b"<html>careers</html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ManualUrlProvider({}, http_client=client, providers_config=_config())

    with pytest.raises(RobotsDisallowedError):
        provider.fetch_page("https://acme.example/careers")


def test_unreachable_robots_txt_is_treated_as_allow_all() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            raise httpx.ConnectError("no robots.txt here", request=request)
        return httpx.Response(200, content=b"<html>ok</html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ManualUrlProvider({}, http_client=client, providers_config=_config())

    page = provider.fetch_page("https://acme.example/")
    assert page.html == "<html>ok</html>"


def test_per_domain_fetch_cap_is_enforced() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, content=b"<html>ok</html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    governor = FetchGovernor(max_pages_per_domain=1, min_seconds_between_requests=0.0)
    provider = ManualUrlProvider(
        {}, http_client=client, governor=governor, providers_config=_config()
    )

    provider.fetch_page("https://acme.example/a")
    with pytest.raises(FetchCapExceededError):
        provider.fetch_page("https://acme.example/b")


def test_respect_robots_txt_false_never_calls_robots_endpoint() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=b"<html>ok</html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ManualUrlProvider(
        {},
        http_client=client,
        providers_config=_config(respect_robots_txt=False),
    )

    provider.fetch_page("https://acme.example/")
    assert calls == ["https://acme.example/"]
