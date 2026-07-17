"""Shared data shapes and exceptions for the public web research pipeline.
Spec §7. Kept in `research/`, not `providers/`, because they're domain
primitives every provider implementation and the orchestrator
(research/pipeline.py) depend on — not implementation details of any one
provider.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from lead_radar.models.enums import EvidenceSourceType


class PageFetchError(Exception):
    """A page could not be fetched (network error, HTTP error, timeout, or
    no fixture registered for the URL). Callers must treat this as a
    skippable per-page failure, not a reason to abort the whole research
    run (spec §7's per-page controls exist precisely so one bad page
    doesn't take down the run)."""


class RobotsDisallowedError(PageFetchError):
    """robots.txt disallows fetching this URL for our user agent (spec §7
    "respect robots restrictions")."""


class FetchCapExceededError(PageFetchError):
    """This domain has already hit max_pages_per_domain for this provider
    instance's lifetime (spec §7 "maximum pages per domain")."""


class FetchedPage(BaseModel):
    """The result of one page fetch, real or fixture-backed."""

    url: str
    final_url: str
    status_code: int
    content_type: str = ""
    html: str
    fetched_at: datetime
    truncated: bool = False
    from_cache: bool = False


class SearchResult(BaseModel):
    """One candidate URL to research, tagged with its role in the spec §7
    source sequence (see research/source_sequence.py) and the
    EvidenceSourceType it will be recorded under."""

    url: str
    title: str = ""
    source_role: str
    source_type: EvidenceSourceType
