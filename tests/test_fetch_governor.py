"""FetchGovernor (per-domain cache/cap/rate-limit) and RobotsPolicy. Spec §7."""

from __future__ import annotations

from datetime import UTC, datetime

from lead_radar.research.fetch_governor import FetchGovernor, RobotsPolicy
from lead_radar.research.models import FetchedPage


def _page(url: str) -> FetchedPage:
    return FetchedPage(
        url=url,
        final_url=url,
        status_code=200,
        html="<html></html>",
        fetched_at=datetime(2026, 7, 17, tzinfo=UTC),
    )


def test_cache_store_and_retrieve_marks_from_cache() -> None:
    governor = FetchGovernor(max_pages_per_domain=8, min_seconds_between_requests=0.0)
    page = _page("https://acme.example/")
    assert governor.cached(page.url) is None

    governor.store(page.url, page)
    cached = governor.cached(page.url)
    assert cached is not None
    assert cached.from_cache is True
    assert cached.url == page.url
    # Original stored page is untouched.
    assert page.from_cache is False


def test_remaining_budget_decreases_with_record_fetch() -> None:
    governor = FetchGovernor(max_pages_per_domain=2, min_seconds_between_requests=0.0)
    assert governor.remaining_budget("acme.example") == 2
    governor.record_fetch("acme.example")
    assert governor.remaining_budget("acme.example") == 1
    governor.record_fetch("acme.example")
    assert governor.remaining_budget("acme.example") == 0


def test_remaining_budget_is_per_domain() -> None:
    governor = FetchGovernor(max_pages_per_domain=1, min_seconds_between_requests=0.0)
    governor.record_fetch("acme.example")
    assert governor.remaining_budget("acme.example") == 0
    assert governor.remaining_budget("other.example") == 1


def test_throttle_is_noop_on_first_fetch_to_a_domain() -> None:
    sleeps: list[float] = []
    governor = FetchGovernor(
        max_pages_per_domain=8,
        min_seconds_between_requests=5.0,
        clock=lambda: 100.0,
        sleep=sleeps.append,
    )
    governor.throttle("acme.example")
    assert sleeps == []


def test_throttle_waits_the_remaining_gap_between_requests() -> None:
    sleeps: list[float] = []
    clock_values = iter([100.0, 101.0])  # record_fetch at t=100, throttle called at t=101
    governor = FetchGovernor(
        max_pages_per_domain=8,
        min_seconds_between_requests=5.0,
        clock=lambda: next(clock_values),
        sleep=sleeps.append,
    )
    governor.record_fetch("acme.example")
    governor.throttle("acme.example")
    assert sleeps == [4.0]


def test_throttle_does_not_wait_once_the_gap_has_elapsed() -> None:
    sleeps: list[float] = []
    clock_values = iter([100.0, 110.0])
    governor = FetchGovernor(
        max_pages_per_domain=8,
        min_seconds_between_requests=5.0,
        clock=lambda: next(clock_values),
        sleep=sleeps.append,
    )
    governor.record_fetch("acme.example")
    governor.throttle("acme.example")
    assert sleeps == []


def test_domain_of_extracts_netloc() -> None:
    assert FetchGovernor.domain_of("https://acme.example/careers?x=1") == "acme.example"


def test_robots_policy_allows_by_default_when_robots_txt_permits() -> None:
    calls = []

    def fetch(origin: str) -> str:
        calls.append(origin)
        return "User-agent: *\nAllow: /\n"

    policy = RobotsPolicy(fetch)
    assert policy.allowed("https://acme.example/careers", "TestBot/1.0") is True
    assert calls == ["https://acme.example"]


def test_robots_policy_disallows_blocked_paths() -> None:
    def fetch(origin: str) -> str:
        return "User-agent: *\nDisallow: /careers\n"

    policy = RobotsPolicy(fetch)
    assert policy.allowed("https://acme.example/careers", "TestBot/1.0") is False
    assert policy.allowed("https://acme.example/", "TestBot/1.0") is True


def test_robots_policy_fetches_robots_txt_once_per_origin() -> None:
    calls = []

    def fetch(origin: str) -> str:
        calls.append(origin)
        return "User-agent: *\nAllow: /\n"

    policy = RobotsPolicy(fetch)
    policy.allowed("https://acme.example/a", "TestBot/1.0")
    policy.allowed("https://acme.example/b", "TestBot/1.0")
    policy.allowed("https://other.example/a", "TestBot/1.0")
    assert calls == ["https://acme.example", "https://other.example"]


def test_robots_policy_treats_empty_robots_txt_as_allow_all() -> None:
    policy = RobotsPolicy(lambda origin: "")
    assert policy.allowed("https://acme.example/anything", "TestBot/1.0") is True
