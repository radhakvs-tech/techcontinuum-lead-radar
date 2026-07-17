"""Per-domain fetch controls shared by every WebResearchProvider
implementation: a fetch cache, a per-domain page cap, a rate limiter, and
robots.txt enforcement. Spec §7: "respect robots restrictions... rate
limits... maximum pages per domain... maintain a per-domain fetch cache."

Deliberately provider-agnostic and network-agnostic: `RobotsPolicy` takes an
injected `fetch_robots_txt` callable rather than doing HTTP itself, so
`MockWebProvider` can exercise the exact same robots-enforcement code path
against fixture text with zero real network calls (see providers/
mock_web_provider.py), and the real HTTP fetch used by `ManualUrlProvider`
is a thin, separately-testable wrapper (providers/manual_url_provider.py).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from lead_radar.research.models import FetchedPage


@dataclass
class _DomainState:
    pages_fetched: int = 0
    last_fetch_monotonic: float | None = None


@dataclass
class FetchGovernor:
    max_pages_per_domain: int
    min_seconds_between_requests: float
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep

    _state: dict[str, _DomainState] = field(default_factory=dict, init=False)
    _cache: dict[str, FetchedPage] = field(default_factory=dict, init=False)

    def cached(self, url: str) -> FetchedPage | None:
        page = self._cache.get(url)
        if page is None:
            return None
        return page.model_copy(update={"from_cache": True})

    def store(self, url: str, page: FetchedPage) -> None:
        self._cache[url] = page

    def _domain_state(self, domain: str) -> _DomainState:
        if domain not in self._state:
            self._state[domain] = _DomainState()
        return self._state[domain]

    def remaining_budget(self, domain: str) -> int:
        return max(0, self.max_pages_per_domain - self._domain_state(domain).pages_fetched)

    def throttle(self, domain: str) -> None:
        """Blocks (via `sleep`) until `min_seconds_between_requests` has
        elapsed since the last fetch to this domain. A no-op on the first
        fetch to any given domain."""
        state = self._domain_state(domain)
        if state.last_fetch_monotonic is None:
            return
        elapsed = self.clock() - state.last_fetch_monotonic
        wait = self.min_seconds_between_requests - elapsed
        if wait > 0:
            self.sleep(wait)

    def record_fetch(self, domain: str) -> None:
        state = self._domain_state(domain)
        state.pages_fetched += 1
        state.last_fetch_monotonic = self.clock()

    @staticmethod
    def domain_of(url: str) -> str:
        return urlsplit(url).netloc


class RobotsPolicy:
    """Wraps `urllib.robotparser.RobotFileParser` per-origin, fetching
    robots.txt at most once per origin for this policy's lifetime via the
    injected `fetch_robots_txt` callable."""

    def __init__(self, fetch_robots_txt: Callable[[str], str | None]) -> None:
        self._fetch_robots_txt = fetch_robots_txt
        self._parsers: dict[str, RobotFileParser] = {}

    def _parser_for_origin(self, origin: str) -> RobotFileParser:
        if origin not in self._parsers:
            robots_text = self._fetch_robots_txt(origin) or ""
            parser = RobotFileParser()
            parser.parse(robots_text.splitlines())
            self._parsers[origin] = parser
        return self._parsers[origin]

    def allowed(self, url: str, user_agent: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        return self._parser_for_origin(origin).can_fetch(user_agent, url)
