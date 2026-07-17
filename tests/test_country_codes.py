"""ISO Alpha-2 normalization for provider country names. Spec §3, §6.

Covers all five of config/icp.yaml's currently-configured
geography.allowed_countries, not just the one (US) confirmed against a
real vpai call — see providers/country_codes.py module docstring."""

from __future__ import annotations

import pytest

from lead_radar.providers.country_codes import normalize_country_to_iso_alpha2
from lead_radar.settings import get_icp_config


def test_allowed_countries_in_icp_config_match_the_five_this_module_covers() -> None:
    """Canary: if icp.yaml's geography ever changes, this fails loudly
    instead of silently leaving a gap in country_codes.py's coverage."""
    assert get_icp_config()["geography"]["allowed_countries"] == ["US", "GB", "DE", "AU", "SG"]


@pytest.mark.parametrize(
    ("country_name", "expected_code"),
    [
        # US: the one name confirmed against a real vpai call this session.
        ("united states", "US"),
        ("United States", "US"),  # case-insensitive
        ("  united states  ", "US"),  # whitespace-tolerant
        ("United States of America", "US"),
        ("USA", "US"),
        ("U.S.A.", "US"),
        # GB, DE, AU, SG: not yet confirmed against a real vpai call for a
        # company headquartered there, but the same normalization must hold.
        ("united kingdom", "GB"),
        ("United Kingdom", "GB"),
        ("UK", "GB"),
        ("great britain", "GB"),
        ("germany", "DE"),
        ("Germany", "DE"),
        ("deutschland", "DE"),
        ("australia", "AU"),
        ("Australia", "AU"),
        ("singapore", "SG"),
        ("Singapore", "SG"),
    ],
)
def test_normalizes_every_configured_country_not_just_us(
    country_name: str, expected_code: str
) -> None:
    assert normalize_country_to_iso_alpha2(country_name) == expected_code


@pytest.mark.parametrize(
    "unmapped_name",
    ["france", "japan", "brazil", "narnia", "not a real country"],
)
def test_unmapped_country_passes_through_unchanged_not_silently_dropped(
    unmapped_name: str,
) -> None:
    """A name outside the five configured countries must NOT be coerced to
    None or guessed at — it must come back unchanged so the downstream
    allowed_countries hard-gate check correctly, visibly rejects it for
    being genuinely out of ICP geography."""
    assert normalize_country_to_iso_alpha2(unmapped_name) == unmapped_name


def test_none_and_empty_input_pass_through_unchanged() -> None:
    assert normalize_country_to_iso_alpha2(None) is None
    assert normalize_country_to_iso_alpha2("") == ""


def test_never_returns_a_code_for_an_unrecognized_name() -> None:
    """A stronger version of the pass-through test: confirm the output is
    never coincidentally one of the five valid codes for an unrelated
    input, which would be a silent false-pass through the geography gate."""
    valid_codes = {"US", "GB", "DE", "AU", "SG"}
    result = normalize_country_to_iso_alpha2("some unrecognized country")
    assert result not in valid_codes
