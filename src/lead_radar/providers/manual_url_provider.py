"""ManualUrlProvider — a WebResearchProvider backed by a human-curated
manifest of URLs and real HTTP fetches. Spec §7.

This is one of two Phase 3a providers that can touch the real network — the
other is `PatternGuessProvider`, which uses it as an explicit fallback. It
only ever fetches URLs a human explicitly added to the manifest — there is
no search/crawl step that discovers new URLs on its own (spec §7 "do not
use uncontrolled crawling"). No test in this repository points this class
at the real network: tests inject `http_client` with an
`httpx.MockTransport`, exactly like `VibeProvider`'s tests inject a fake
`VpaiRunner` instead of shelling out to `vpai` (see providers/
vibe_provider.py). The real `httpx.Client` default is only ever exercised
by a human deliberately running the `research` CLI command against a
manifest they populated themselves.
"""

from __future__ import annotations

import httpx

from lead_radar.providers.web_research_base import WebResearchProviderBase
from lead_radar.research.fetch_governor import FetchGovernor
from lead_radar.research.http_fetch import RealPageFetcher
from lead_radar.research.models import FetchedPage, SearchResult
from lead_radar.research.source_sequence import ROLE_SOURCE_TYPES, ordered_roles
from lead_radar.settings import YamlConfig, get_providers_config

# A human-curated manifest: {domain: {role: [url, ...]}}. Roles are the
# research/source_sequence.py role keys (homepage, careers_page, ...).
ManualUrlManifest = dict[str, dict[str, list[str]]]


class ManualUrlProvider(WebResearchProviderBase):
    name = "manual_url"

    def __init__(
        self,
        manifest: ManualUrlManifest,
        *,
        governor: FetchGovernor | None = None,
        http_client: httpx.Client | None = None,
        providers_config: YamlConfig | None = None,
    ) -> None:
        config = providers_config or get_providers_config()
        web_cfg = config["web_research"]

        self._manifest = manifest
        governor = governor or FetchGovernor(
            max_pages_per_domain=int(web_cfg["max_pages_per_domain"]),
            min_seconds_between_requests=float(web_cfg["min_seconds_between_requests_per_domain"]),
        )
        client = http_client or httpx.Client(
            timeout=float(web_cfg["page_fetch_timeout_seconds"]),
            follow_redirects=True,
            headers={"User-Agent": web_cfg["user_agent"]},
        )
        self._fetcher = RealPageFetcher(
            governor=governor,
            http_client=client,
            user_agent=web_cfg["user_agent"],
            max_content_size_bytes=int(web_cfg["max_content_size_bytes"]),
            respect_robots=bool(web_cfg["respect_robots_txt"]),
        )

    def search(self, domain: str, roles: list[str] | None = None) -> list[SearchResult]:
        role_urls = self._manifest.get(domain, {})
        results: list[SearchResult] = []
        for role in roles or ordered_roles():
            source_type = ROLE_SOURCE_TYPES[role]
            for url in role_urls.get(role, []):
                results.append(
                    SearchResult(url=url, title=url, source_role=role, source_type=source_type)
                )
        return results

    def fetch_page(self, url: str) -> FetchedPage:
        return self._fetcher.fetch(url)
