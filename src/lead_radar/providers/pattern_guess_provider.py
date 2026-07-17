"""PatternGuessProvider — goes from "known domain" straight to "the right
pages to fetch" by trying conventional URL path patterns per spec §7
source-sequence role, without a human curating a manifest first. Spec §7,
§20 Phase 3a.

This is what the intended weekly production flow needs that
`ManualUrlProvider` alone doesn't provide: `ManualUrlProvider` only ever
fetches URLs a human already supplied. `PatternGuessProvider` instead tries
a small set of conventional paths (`/careers`, `/changelog`, ...) per role,
validates each candidate with a real fetch (200 OK *and* a basic
company-name check against the page's title/meta description — see
`_matches_company`), and falls back to an internal `ManualUrlProvider` for
any role no pattern resolved.

The company-name check exists because a 200 response alone proves nothing:
this session's manual validation hit exactly that failure mode for real —
`gozen.com/jobs` returned 200 but is an unrelated company that happens to
share the "GoZen" name with `gozen.io`, the one this pipeline actually
cares about. Guessed URLs get no other verification beyond that check —
see docs/architecture.md "Known limitations" for what that does and
doesn't catch.

No test in this repository points this class at the real network — see
providers/manual_url_provider.py's module docstring for why that pattern
matters here too.
"""

from __future__ import annotations

import re

import httpx

from lead_radar.providers.manual_url_provider import ManualUrlManifest, ManualUrlProvider
from lead_radar.providers.web_research_base import WebResearchProviderBase
from lead_radar.research.evidence_extraction import parse_structure
from lead_radar.research.fetch_governor import FetchGovernor
from lead_radar.research.http_fetch import RealPageFetcher
from lead_radar.research.models import (
    FetchCapExceededError,
    FetchedPage,
    PageFetchError,
    SearchResult,
)
from lead_radar.research.source_sequence import ROLE_GITHUB, ROLE_SOURCE_TYPES, ordered_roles
from lead_radar.settings import YamlConfig, get_providers_config, get_url_patterns_config

# domain -> the company name expected on that domain's pages. Optional per
# domain: when a domain has no entry, its first dot-separated label (e.g.
# "hasura" from "hasura.io") is used as a weaker stand-in — verification
# still runs, just against a cruder expected name.
CompanyNameMap = dict[str, str]

_MIN_MATCH_TOKEN_LENGTH = 3


class PatternGuessProvider(WebResearchProviderBase):
    name = "pattern_guess"

    def __init__(
        self,
        company_names: CompanyNameMap | None = None,
        *,
        fallback_manifest: ManualUrlManifest | None = None,
        governor: FetchGovernor | None = None,
        http_client: httpx.Client | None = None,
        providers_config: YamlConfig | None = None,
        url_patterns_config: YamlConfig | None = None,
    ) -> None:
        config = providers_config or get_providers_config()
        web_cfg = config["web_research"]
        patterns_config = url_patterns_config or get_url_patterns_config()

        self._company_names = company_names or {}
        self._patterns: dict[str, list[str]] = patterns_config.get("role_path_patterns", {})
        self._github_slug_variants: list[str] = patterns_config.get(
            "github_org_slug_variants", ["{label}"]
        )

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
        # Same governor + http_client as this instance's own guessing, so a
        # page already validated while pattern-guessing is a free cache hit
        # for the fallback (and vice versa), and both share one per-domain
        # fetch budget/rate limit for the run rather than two independent
        # ones.
        self._manual_fallback = ManualUrlProvider(
            fallback_manifest or {}, governor=governor, http_client=client, providers_config=config
        )

    def _expected_name(self, domain: str) -> str:
        return self._company_names.get(domain) or domain.split(".")[0]

    def _matches_company(self, page: FetchedPage, expected_name: str) -> bool:
        name = expected_name.lower().strip()
        if not name:
            return True
        structure = parse_structure(page.html)
        haystack = " ".join(
            part
            for part in (
                structure.title,
                structure.meta.get("description"),
                structure.meta.get("og:description"),
            )
            if part
        ).lower()
        if name in haystack:
            return True
        tokens = [t for t in re.split(r"[^a-z0-9]+", name) if len(t) >= _MIN_MATCH_TOKEN_LENGTH]
        return bool(tokens) and all(token in haystack for token in tokens)

    def _guess_role(self, domain: str, role: str, expected_name: str) -> SearchResult | None:
        for path in self._patterns.get(role, []):
            url = f"https://{domain}{path}"
            try:
                page = self._fetcher.fetch(url)
            except FetchCapExceededError:
                return None
            except PageFetchError:
                continue
            if self._matches_company(page, expected_name):
                return SearchResult(
                    url=url, title=path, source_role=role, source_type=ROLE_SOURCE_TYPES[role]
                )
        return None

    def _guess_github(self, expected_name: str) -> SearchResult | None:
        label = re.sub(r"[^a-z0-9-]", "", expected_name.lower())
        if not label:
            return None
        for variant in self._github_slug_variants:
            slug = variant.format(label=label)
            url = f"https://github.com/{slug}"
            try:
                page = self._fetcher.fetch(url)
            except FetchCapExceededError:
                return None
            except PageFetchError:
                continue
            if self._matches_company(page, expected_name):
                return SearchResult(
                    url=url,
                    title=slug,
                    source_role=ROLE_GITHUB,
                    source_type=ROLE_SOURCE_TYPES[ROLE_GITHUB],
                )
        return None

    def search(self, domain: str, roles: list[str] | None = None) -> list[SearchResult]:
        expected_name = self._expected_name(domain)
        roles = roles or ordered_roles()

        guessed_by_role: dict[str, SearchResult] = {}
        unresolved_roles: list[str] = []
        for role in roles:
            hit = (
                self._guess_github(expected_name)
                if role == ROLE_GITHUB
                else self._guess_role(domain, role, expected_name)
            )
            if hit is not None:
                guessed_by_role[role] = hit
            else:
                unresolved_roles.append(role)

        manual_by_role: dict[str, list[SearchResult]] = {}
        if unresolved_roles:
            for result in self._manual_fallback.search(domain, roles=unresolved_roles):
                manual_by_role.setdefault(result.source_role, []).append(result)

        # Preserve the caller's requested role order (spec §7's source
        # sequence) rather than "all guessed hits, then all fallback hits" —
        # a manually-supplied changelog URL must still sort before a
        # guessed careers-page hit if changelog comes first in the sequence.
        ordered: list[SearchResult] = []
        for role in roles:
            if role in guessed_by_role:
                ordered.append(guessed_by_role[role])
            else:
                ordered.extend(manual_by_role.get(role, []))
        return ordered

    def fetch_page(self, url: str) -> FetchedPage:
        return self._fetcher.fetch(url)
