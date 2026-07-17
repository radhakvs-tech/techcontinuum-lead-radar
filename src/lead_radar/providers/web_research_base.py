"""Public web research provider abstraction. Spec §7.

`WebResearchProvider` is implemented by `ManualUrlProvider` (real HTTP,
never invoked live in this codebase without explicit go-ahead) and
`MockWebProvider` (offline fixtures, used everywhere in tests). Both share
`extract_public_evidence` via `WebResearchProviderBase` — structural
keyword extraction (research/evidence_extraction.py) doesn't depend on how
a page was fetched, only on its HTML, so it lives in exactly one place
rather than being duplicated per provider.
"""

from __future__ import annotations

from typing import Protocol

from lead_radar.models.enums import EvidenceSourceType
from lead_radar.models.evidence import Evidence
from lead_radar.research.evidence_extraction import extract_public_evidence
from lead_radar.research.models import FetchedPage, SearchResult

__all__ = [
    "FetchedPage",
    "SearchResult",
    "WebResearchProvider",
    "WebResearchProviderBase",
]


class WebResearchProvider(Protocol):
    name: str

    def search(self, domain: str, roles: list[str] | None = None) -> list[SearchResult]: ...

    def fetch_page(self, url: str) -> FetchedPage: ...

    def extract_public_evidence(
        self, account_id: int, page: FetchedPage, source_type: EvidenceSourceType
    ) -> list[Evidence]: ...


class WebResearchProviderBase:
    """Shared `extract_public_evidence`. Subclasses implement `search` and
    `fetch_page` only."""

    name = "web_research_base"

    def extract_public_evidence(
        self, account_id: int, page: FetchedPage, source_type: EvidenceSourceType
    ) -> list[Evidence]:
        return extract_public_evidence(account_id, page, source_type)
