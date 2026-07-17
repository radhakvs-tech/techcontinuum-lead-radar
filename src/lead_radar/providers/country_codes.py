"""ISO Alpha-2 country-code normalization for provider data. Spec §3, §6.

vpai returns full, lowercase country names in `country_name` fields (e.g.
"united states") — confirmed via a real call, see
providers/vibe_provider.py's module docstring. config/icp.yaml
`geography.allowed_countries`, and the hard-gate check in
discovery/hard_gates.py, expect ISO Alpha-2 codes ("US"). Without
normalization, every real VibeProvider company record silently failed the
geography hard gate regardless of actual country fit — discovered when a
real Google ingest was rejected for "headquarters_country 'united states'
is outside the configured geography ['US', 'GB', 'DE', 'AU', 'SG']", even
though "united states" plainly is "US".

This maps the name variants vpai is expected to return for each of
icp.yaml's currently-configured countries to their ISO Alpha-2 code.
**Only "united states" -> "US" has been confirmed against real vpai
output** (the one country the codebase has actually ingested a live
record for so far). The other four countries' name variants are built
from their standard English short/formal names and common abbreviations,
not yet independently verified against a real vpai call for those
countries specifically — flagged the same way every other unverified
VibeProvider field-name assumption is (see vibe_provider.py's module
docstring "What's verified vs. inferred"). Re-validate each one the first
time a real company headquartered there is actually ingested.

Deliberately NOT a general-purpose global ISO-3166 lookup — pulling in a
dependency (e.g. `pycountry`) for this wasn't justified since none was
already a project dependency and the actual need is narrow: only
icp.yaml's five currently-configured countries need to resolve. If that
list grows, add the new code's name variants here too and keep this
module's `_ISO_ALPHA2_NAME_VARIANTS` keys in sync with
config/icp.yaml `geography.allowed_countries` — an unmapped name is not a
bug, it is correctly, safely treated as out-of-geography (see
`normalize_country_to_iso_alpha2`'s docstring): this module never guesses
a code for a name it doesn't recognize.
"""

from __future__ import annotations

import re

# ISO Alpha-2 code -> known name variants a provider might return for it.
# Keys must stay in sync with config/icp.yaml geography.allowed_countries.
_ISO_ALPHA2_NAME_VARIANTS: dict[str, list[str]] = {
    # CONFIRMED against real vpai output this session.
    "US": ["united states", "united states of america", "usa", "u.s.a.", "u.s.", "us"],
    # Not yet confirmed against a real vpai call for a GB/DE/AU/SG-based
    # company — built from standard English short/formal names plus common
    # abbreviations.
    "GB": ["united kingdom", "great britain", "uk", "u.k.", "gb"],
    "DE": ["germany", "deutschland", "de"],
    "AU": ["australia", "au"],
    "SG": ["singapore", "sg"],
}


def _clean(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[.’']", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


_NAME_TO_ISO_ALPHA2: dict[str, str] = {
    _clean(name): code for code, names in _ISO_ALPHA2_NAME_VARIANTS.items() for name in names
}


def normalize_country_to_iso_alpha2(country_name: str | None) -> str | None:
    """Best-effort map a free-text country name to its ISO Alpha-2 code.

    Returns the ORIGINAL, unmodified input when no mapping is found —
    never a guessed code, never coerced to None — so an unmapped name
    still correctly fails config/icp.yaml's `allowed_countries` check
    downstream (a hard, correct rejection for being genuinely
    out-of-geography) instead of silently vanishing or, worse,
    accidentally matching a code it doesn't actually correspond to.
    """
    if not country_name:
        return country_name
    return _NAME_TO_ISO_ALPHA2.get(_clean(country_name), country_name)
