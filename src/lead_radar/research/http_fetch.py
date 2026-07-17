"""Real HTTP page fetching, shared by `ManualUrlProvider` and
`PatternGuessProvider`. Spec §7.

Both providers need identical network-safety behaviour (fetch cache,
per-domain cap, rate limiting, robots.txt, timeouts, content-size cap) —
this is that one implementation, so the two providers can never drift
apart on what "safe" means. Extracted from what was originally
`ManualUrlProvider.fetch_page` once `PatternGuessProvider` needed the exact
same logic for its own validation fetches.

Like `ManualUrlProvider`, real network access here is never exercised by
this repo's own tests: every test injects an `httpx.MockTransport`-backed
client.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from lead_radar.research.fetch_governor import FetchGovernor, RobotsPolicy
from lead_radar.research.models import (
    FetchCapExceededError,
    FetchedPage,
    PageFetchError,
    RobotsDisallowedError,
)


class RealPageFetcher:
    def __init__(
        self,
        *,
        governor: FetchGovernor,
        http_client: httpx.Client,
        user_agent: str,
        max_content_size_bytes: int,
        respect_robots: bool,
    ) -> None:
        self._governor = governor
        self._client = http_client
        self._user_agent = user_agent
        self._max_content_size_bytes = max_content_size_bytes
        self._robots = RobotsPolicy(self._fetch_robots_txt) if respect_robots else None

    def _fetch_robots_txt(self, origin: str) -> str | None:
        """An unreachable or erroring robots.txt is treated as allow-all —
        standard crawler practice, and the conservative choice here would
        be the opposite of safe (silently researching nothing because a
        site has no robots.txt at all is not the failure mode we want)."""
        try:
            response = self._client.get(f"{origin}/robots.txt")
        except httpx.HTTPError:
            return ""
        if response.status_code >= 400:
            return ""
        return response.text

    def fetch(self, url: str) -> FetchedPage:
        domain = FetchGovernor.domain_of(url)

        cached = self._governor.cached(url)
        if cached is not None:
            return cached

        if self._governor.remaining_budget(domain) <= 0:
            raise FetchCapExceededError(f"max_pages_per_domain reached for {domain!r}")

        if self._robots is not None and not self._robots.allowed(url, self._user_agent):
            raise RobotsDisallowedError(f"robots.txt disallows fetching {url}")

        self._governor.throttle(domain)

        try:
            with self._client.stream("GET", url) as response:
                response.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                truncated = False
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self._max_content_size_bytes:
                        truncated = True
                        break
                    chunks.append(chunk)
                html = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
                page = FetchedPage(
                    url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type", ""),
                    html=html,
                    fetched_at=datetime.now(UTC),
                    truncated=truncated,
                )
        except httpx.HTTPError as exc:
            raise PageFetchError(f"{type(exc).__name__} fetching {url}: {exc}") from exc

        self._governor.record_fetch(domain)
        self._governor.store(url, page)
        return page
