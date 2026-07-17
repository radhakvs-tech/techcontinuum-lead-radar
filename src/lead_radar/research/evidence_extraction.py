"""Structural, keyword-based evidence extraction. Spec §5, §7, §20
(Phase 3a: "structural/keyword-based classification only — genuine
judgment-based classification is Phase 3b's job").

No LLM call happens anywhere in this module. A page's HTML is parsed for
structure (headings, paragraph-like text blocks, publish dates from
<meta>/<time> tags), each text block is checked against
config/evidence_keywords.yaml's phrase lists, and a match is classified
into one of the four spec §5 evidence tiers using only: which signal_type
phrase matched, which EvidenceSourceType the page came from, and whether
hedging language is present in the same block. That's a fixed, inspectable
rule table — not judgment.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from html.parser import HTMLParser

from lead_radar.models.enums import EvidenceClassification, EvidenceSourceType
from lead_radar.models.evidence import Evidence
from lead_radar.research.models import FetchedPage
from lead_radar.settings import YamlConfig, get_evidence_keywords_config

_BLOCK_TAGS = {"p", "li", "td", "blockquote"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_SKIP_TAGS = {"script", "style", "noscript"}

_MONTH_NAMES = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
_MONTH_DATE_RE = re.compile(rf"\b(?:{_MONTH_NAMES})\s+\d{{1,2}},?\s+\d{{4}}\b")
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

# Evidence tier -> heuristic confidence. Fixed, not learned — a Phase 3a
# structural match is never as trustworthy as a Phase 3b LLM-verified one,
# so these stay conservative.
_CONFIDENCE_BY_TIER: dict[EvidenceClassification, float] = {
    EvidenceClassification.OBSERVED_FACT: 0.75,
    EvidenceClassification.REASONABLE_INFERENCE: 0.55,
    EvidenceClassification.GENERAL_INDUSTRY_CONSIDERATION: 0.3,
    EvidenceClassification.UNKNOWN_REQUIRING_VALIDATION: 0.35,
}

GENERIC_MARKETING_SIGNAL = "generic_ai_marketing_only"


class PageStructure:
    def __init__(self) -> None:
        self.title: str | None = None
        self.meta: dict[str, str] = {}
        self.time_tags: list[str] = []
        # Ordered (heading_text_or_none, block_text) pairs — each block
        # paired with the nearest preceding heading, for evidence_summary.
        self.blocks: list[tuple[str | None, str]] = []


class _StructuralHTMLParser(HTMLParser):
    """Deliberately minimal: headings, block-level text, <meta> and <time>
    tags only. No JS execution, no CSS, no external fetches — this parses
    exactly the bytes already fetched by the provider."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.structure = PageStructure()
        self._in_title = False
        self._skip_depth = 0
        self._current_heading: str | None = None
        self._last_heading: str | None = None
        self._buffer: list[str] = []
        self._buffering = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k: v for k, v in attrs if v is not None}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = attr_dict.get("name") or attr_dict.get("property")
            content = attr_dict.get("content")
            if name and content:
                self.structure.meta[name.lower()] = content
        elif tag == "time":
            dt = attr_dict.get("datetime")
            if dt:
                self.structure.time_tags.append(dt)
        elif tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _HEADING_TAGS:
            self._buffering = True
            self._buffer = []
        elif tag in _BLOCK_TAGS:
            self._buffering = True
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _HEADING_TAGS:
            text = "".join(self._buffer).strip()
            self._buffering = False
            self._buffer = []
            if text:
                self._last_heading = text
        elif tag in _BLOCK_TAGS:
            text = "".join(self._buffer).strip()
            self._buffering = False
            self._buffer = []
            if text:
                self.structure.blocks.append((self._last_heading, text))

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.structure.title = (self.structure.title or "") + data
        if self._buffering:
            self._buffer.append(data)


def parse_structure(html: str) -> PageStructure:
    parser = _StructuralHTMLParser()
    parser.feed(html)
    structure = parser.structure
    if structure.title is not None:
        structure.title = " ".join(structure.title.split())
    return structure


def _parse_date_like(text: str) -> date | None:
    iso_match = _ISO_DATE_RE.search(text)
    if iso_match:
        try:
            return date.fromisoformat(iso_match.group(0))
        except ValueError:
            pass
    month_match = _MONTH_DATE_RE.search(text)
    if month_match:
        cleaned = month_match.group(0).replace(",", "")
        for fmt in ("%B %d %Y",):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
    return None


def resolve_page_date(structure: PageStructure) -> date | None:
    """Best-effort published_date: an explicit <meta> publish-date field
    wins, then the first <time datetime="...">, then nothing — never
    invented from an unrelated date string elsewhere on the page."""
    for key in ("article:published_time", "og:published_time", "date", "publish-date"):
        value = structure.meta.get(key)
        if value:
            parsed = _parse_date_like(value) or _parse_date_like(value[:10])
            if parsed:
                return parsed
    for raw in structure.time_tags:
        parsed = _parse_date_like(raw)
        if parsed:
            return parsed
    return None


def _independence_group(source_url: str) -> str:
    """All evidence extracted from the same page shares one independence
    group — spec §5's "two signals from the same [document] do not count
    as independent" applies just as much to two keyword matches on one
    page as it does to syndicated press coverage."""
    import hashlib

    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]


def _match_signal(
    lower_block: str,
    signal_keywords: dict[str, list[str]],
) -> tuple[str, str] | None:
    for signal_type, phrases in signal_keywords.items():
        if signal_type == GENERIC_MARKETING_SIGNAL:
            continue
        for phrase in phrases:
            if phrase.lower() in lower_block:
                return signal_type, phrase
    return None


def _match_generic_marketing(lower_block: str, generic_phrases: list[str]) -> str | None:
    for phrase in generic_phrases:
        if phrase.lower() in lower_block:
            return phrase
    return None


def _classify_tier(
    *,
    signal_type: str,
    source_type: EvidenceSourceType,
    is_hedged: bool,
    observed_fact_source_types: set[str],
) -> EvidenceClassification:
    if signal_type == GENERIC_MARKETING_SIGNAL:
        return EvidenceClassification.GENERAL_INDUSTRY_CONSIDERATION
    if is_hedged:
        return EvidenceClassification.UNKNOWN_REQUIRING_VALIDATION
    if source_type.value in observed_fact_source_types:
        return EvidenceClassification.OBSERVED_FACT
    return EvidenceClassification.REASONABLE_INFERENCE


def extract_public_evidence(
    account_id: int,
    page: FetchedPage,
    source_type: EvidenceSourceType,
    keywords_config: YamlConfig | None = None,
) -> list[Evidence]:
    config = keywords_config or get_evidence_keywords_config()
    signal_keywords: dict[str, list[str]] = config["signal_keywords"]
    generic_phrases: list[str] = config.get("generic_marketing_phrases", [])
    hedge_phrases: list[str] = config.get("hedge_phrases", [])
    observed_fact_source_types: set[str] = set(config.get("observed_fact_source_types", []))

    structure = parse_structure(page.html)
    page_date = resolve_page_date(structure)
    independence_group = _independence_group(page.url)
    source_title = structure.title or page.url

    evidence_rows: list[Evidence] = []
    seen: set[tuple[str, str]] = set()

    for heading, block_text in structure.blocks:
        lower_block = block_text.lower()

        match = _match_signal(lower_block, signal_keywords)
        if match is not None:
            signal_type, _phrase = match
        else:
            generic_match = _match_generic_marketing(lower_block, generic_phrases)
            if generic_match is None:
                continue
            signal_type = GENERIC_MARKETING_SIGNAL

        dedup_key = (signal_type, block_text[:200])
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        is_hedged = any(hedge.lower() in lower_block for hedge in hedge_phrases)
        classification = _classify_tier(
            signal_type=signal_type,
            source_type=source_type,
            is_hedged=is_hedged,
            observed_fact_source_types=observed_fact_source_types,
        )

        evidence_rows.append(
            Evidence(
                account_id=account_id,
                source_url=page.url,
                source_title=source_title,
                source_type=source_type,
                published_date=page_date,
                observed_date=page.fetched_at.astimezone(UTC).date(),
                evidence_text=block_text[:2000],
                evidence_summary=(heading or block_text)[:200],
                signal_type=signal_type,
                classification=classification,
                confidence=_CONFIDENCE_BY_TIER[classification],
                independence_group=independence_group,
            )
        )

    return evidence_rows
