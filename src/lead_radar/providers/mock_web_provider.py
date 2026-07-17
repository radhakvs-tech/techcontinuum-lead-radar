"""MockWebProvider — offline, fixture-backed WebResearchProvider. Spec §7.

No network access at all: pages and search results are supplied directly
as fixtures by the caller. Used for tests and for exercising the whole
research pipeline (source sequence, fetch cache, per-domain cap, rate
limiting, robots enforcement, structural evidence extraction) before ever
pointing ManualUrlProvider at a real URL — per this session's explicit
instruction to build and validate everything against mocks first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from lead_radar.providers.web_research_base import WebResearchProviderBase
from lead_radar.research.fetch_governor import FetchGovernor, RobotsPolicy
from lead_radar.research.models import (
    FetchCapExceededError,
    FetchedPage,
    PageFetchError,
    RobotsDisallowedError,
    SearchResult,
)
from lead_radar.research.source_sequence import ordered_roles
from lead_radar.settings import YamlConfig, get_providers_config


@dataclass
class FixturePage:
    html: str
    status_code: int = 200
    content_type: str = "text/html"


@dataclass
class MockWebProviderFixtures:
    pages: dict[str, FixturePage] = field(default_factory=dict)
    search_results: dict[str, list[SearchResult]] = field(default_factory=dict)
    # {origin ("https://example.example"): robots.txt text}. Missing entries
    # default to allow-all, same as ManualUrlProvider's unreachable-robots
    # fallback, so tests only need to populate this when exercising a
    # disallow case.
    robots_txt: dict[str, str] = field(default_factory=dict)


class MockWebProvider(WebResearchProviderBase):
    name = "mock_web"

    def __init__(
        self,
        fixtures: MockWebProviderFixtures,
        *,
        governor: FetchGovernor | None = None,
        user_agent: str | None = None,
        respect_robots_txt: bool | None = None,
        providers_config: YamlConfig | None = None,
    ) -> None:
        config = providers_config or get_providers_config()
        web_cfg = config["web_research"]

        self._fixtures = fixtures
        self._user_agent = user_agent or web_cfg["user_agent"]
        self._respect_robots = (
            respect_robots_txt
            if respect_robots_txt is not None
            else bool(web_cfg["respect_robots_txt"])
        )
        self._governor = governor or FetchGovernor(
            max_pages_per_domain=int(web_cfg["max_pages_per_domain"]),
            min_seconds_between_requests=float(web_cfg["min_seconds_between_requests_per_domain"]),
        )
        self._robots = RobotsPolicy(self._fetch_robots_txt) if self._respect_robots else None

    def _fetch_robots_txt(self, origin: str) -> str | None:
        return self._fixtures.robots_txt.get(origin, "")

    def search(self, domain: str, roles: list[str] | None = None) -> list[SearchResult]:
        available = self._fixtures.search_results.get(domain, [])
        by_role: dict[str, list[SearchResult]] = {}
        for result in available:
            by_role.setdefault(result.source_role, []).append(result)
        ordered: list[SearchResult] = []
        for role in roles or ordered_roles():
            ordered.extend(by_role.get(role, []))
        return ordered

    def fetch_page(self, url: str) -> FetchedPage:
        domain = FetchGovernor.domain_of(url)

        cached = self._governor.cached(url)
        if cached is not None:
            return cached

        if self._governor.remaining_budget(domain) <= 0:
            raise FetchCapExceededError(f"max_pages_per_domain reached for {domain!r}")

        if self._robots is not None and not self._robots.allowed(url, self._user_agent):
            raise RobotsDisallowedError(f"robots.txt disallows fetching {url}")

        self._governor.throttle(domain)

        fixture = self._fixtures.pages.get(url)
        if fixture is None:
            raise PageFetchError(f"no fixture registered for {url}")

        page = FetchedPage(
            url=url,
            final_url=url,
            status_code=fixture.status_code,
            content_type=fixture.content_type,
            html=fixture.html,
            fetched_at=datetime.now(UTC),
            truncated=False,
        )
        self._governor.record_fetch(domain)
        self._governor.store(url, page)
        return page
