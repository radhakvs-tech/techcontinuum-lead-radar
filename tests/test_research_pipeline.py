"""research/pipeline.py:run_research — the Phase 3a orchestrator. Spec §7.

Runs entirely against MockWebProvider fixtures; no network access.
"""

from __future__ import annotations

import pytest
from conftest import make_account
from sqlmodel import Session, select

from lead_radar.models.account import Account
from lead_radar.models.enums import AccountStatus, Classification, EvidenceSourceType, ReviewerLabel
from lead_radar.models.evidence import Evidence
from lead_radar.models.research import ResearchRun
from lead_radar.models.review import HumanReview
from lead_radar.models.scoring import ScoreRun
from lead_radar.providers.mock_web_provider import (
    FixturePage,
    MockWebProvider,
    MockWebProviderFixtures,
)
from lead_radar.research.models import SearchResult
from lead_radar.research.pipeline import run_research
from lead_radar.research.source_sequence import (
    ROLE_CAREERS_PAGE,
    ROLE_CHANGELOG,
    ROLE_HOMEPAGE,
)
from lead_radar.settings import YamlConfig

_CONFIG = YamlConfig(
    data={
        "web_research": {
            "active_provider": "mock",
            "max_pages_per_domain": 8,
            "page_fetch_timeout_seconds": 15,
            "max_content_size_bytes": 2_000_000,
            "respect_robots_txt": True,
            "min_seconds_between_requests_per_domain": 0.0,
            "preliminary_score_threshold": 45,
            "user_agent": "TestBot/1.0",
            "manual_url_manifest_path": "data/imports/manual_research_urls.yaml",
        }
    }
)


def _score_run(account_id: int, total_score: float) -> ScoreRun:
    return ScoreRun(
        account_id=account_id,
        scoring_version="test",
        total_score=total_score,
        classification=Classification.WATCHLIST,
    )


def test_skips_when_no_score_run_exists(session: Session) -> None:
    account = make_account(session, domain="acme.example")
    provider = MockWebProvider(MockWebProviderFixtures(), providers_config=_CONFIG)

    result = run_research(session, account, provider, providers_config=_CONFIG)

    assert result.status == "skipped"
    assert "no ScoreRun" in (result.skipped_reason or "")


def test_skips_when_score_below_threshold(session: Session) -> None:
    account = make_account(session, domain="acme.example")
    session.add(_score_run(account.id, total_score=10.0))
    session.commit()
    provider = MockWebProvider(MockWebProviderFixtures(), providers_config=_CONFIG)

    result = run_research(session, account, provider, providers_config=_CONFIG)

    assert result.status == "skipped"
    assert "below" in (result.skipped_reason or "")


def test_skips_rejected_accounts_even_with_a_high_score(session: Session) -> None:
    account = make_account(session, domain="acme.example", status=AccountStatus.REJECTED)
    session.add(_score_run(account.id, total_score=90.0))
    session.commit()
    provider = MockWebProvider(MockWebProviderFixtures(), providers_config=_CONFIG)

    result = run_research(session, account, provider, providers_config=_CONFIG)

    assert result.status == "skipped"
    assert "rejected" in (result.skipped_reason or "")


def test_runs_and_persists_evidence_and_research_run_when_above_threshold(
    session: Session,
) -> None:
    account = make_account(session, domain="acme.example")
    session.add(_score_run(account.id, total_score=70.0))
    session.commit()

    fixtures = MockWebProviderFixtures(
        search_results={
            "acme.example": [
                SearchResult(
                    url="https://acme.example/",
                    source_role=ROLE_HOMEPAGE,
                    source_type=EvidenceSourceType.COMPANY_WEBSITE,
                ),
                SearchResult(
                    url="https://acme.example/careers",
                    source_role=ROLE_CAREERS_PAGE,
                    source_type=EvidenceSourceType.CAREERS_PAGE,
                ),
            ]
        },
        pages={
            "https://acme.example/": FixturePage(
                html="<html><body><p>We build great software.</p></body></html>"
            ),
            "https://acme.example/careers": FixturePage(
                html="<html><body><p>Hiring a Site Reliability Engineer now.</p></body></html>"
            ),
        },
    )
    provider = MockWebProvider(fixtures, providers_config=_CONFIG)

    result = run_research(session, account, provider, providers_config=_CONFIG)

    assert result.status == "completed"
    assert result.pages_fetched == 2
    assert len(result.evidence) == 1  # only the careers page matched a keyword
    assert result.evidence[0].signal_type == "platform_or_sre_hiring"

    persisted = list(session.exec(select(Evidence).where(Evidence.account_id == account.id)))
    assert len(persisted) == 1

    research_runs = list(
        session.exec(select(ResearchRun).where(ResearchRun.account_id == account.id))
    )
    assert len(research_runs) == 1
    assert research_runs[0].provider == "mock_web"
    assert research_runs[0].pages_fetched == 2

    session.refresh(account)
    assert account.status == AccountStatus.RESEARCHED


def test_source_sequence_order_is_respected_when_fetching(session: Session) -> None:
    account = make_account(session, domain="acme.example")
    session.add(_score_run(account.id, total_score=70.0))
    session.commit()

    fixtures = MockWebProviderFixtures(
        search_results={
            "acme.example": [
                # Deliberately registered out of source-sequence order.
                SearchResult(
                    url="https://acme.example/changelog",
                    source_role=ROLE_CHANGELOG,
                    source_type=EvidenceSourceType.CHANGELOG,
                ),
                SearchResult(
                    url="https://acme.example/",
                    source_role=ROLE_HOMEPAGE,
                    source_type=EvidenceSourceType.COMPANY_WEBSITE,
                ),
            ]
        },
        pages={
            "https://acme.example/changelog": FixturePage(html="<html></html>"),
            "https://acme.example/": FixturePage(html="<html></html>"),
        },
    )
    fetch_order: list[str] = []
    provider = MockWebProvider(fixtures, providers_config=_CONFIG)
    original_fetch_page = provider.fetch_page

    def spying_fetch_page(url: str):  # type: ignore[no-untyped-def]
        fetch_order.append(url)
        return original_fetch_page(url)

    provider.fetch_page = spying_fetch_page  # type: ignore[method-assign]

    run_research(session, account, provider, providers_config=_CONFIG)

    assert fetch_order == ["https://acme.example/", "https://acme.example/changelog"]


def test_unfetchable_page_is_skipped_not_fatal(session: Session) -> None:
    account = make_account(session, domain="acme.example")
    session.add(_score_run(account.id, total_score=70.0))
    session.commit()

    fixtures = MockWebProviderFixtures(
        search_results={
            "acme.example": [
                SearchResult(
                    url="https://acme.example/missing",
                    source_role=ROLE_HOMEPAGE,
                    source_type=EvidenceSourceType.COMPANY_WEBSITE,
                ),
            ]
        },
        pages={},  # no fixture registered -> PageFetchError inside fetch_page
    )
    provider = MockWebProvider(fixtures, providers_config=_CONFIG)

    result = run_research(session, account, provider, providers_config=_CONFIG)

    assert result.status == "completed"
    assert result.pages_fetched == 0
    assert len(result.pages_skipped) == 1
    assert "https://acme.example/missing" in result.pages_skipped[0]


def test_human_reviewed_account_status_is_not_overwritten(session: Session) -> None:
    account = make_account(
        session, domain="acme.example", status=AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY
    )
    session.add(_score_run(account.id, total_score=70.0))
    session.add(
        HumanReview(
            account_id=account.id,
            reviewer="reviewer@example.com",
            old_status=AccountStatus.PENDING_HUMAN_REVIEW,
            new_status=AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY,
            reviewer_label=ReviewerLabel.HIGH_PRIORITY,
            reason="strong evidence",
        )
    )
    session.commit()

    provider = MockWebProvider(MockWebProviderFixtures(), providers_config=_CONFIG)
    result = run_research(session, account, provider, providers_config=_CONFIG)

    assert result.status == "completed"
    session.refresh(account)
    assert account.status == AccountStatus.APPROVED_FOR_CONTACT_DISCOVERY


def test_raises_when_account_is_not_persisted() -> None:
    unpersisted = Account(domain="acme.example", company_name="Acme")
    provider = MockWebProvider(MockWebProviderFixtures(), providers_config=_CONFIG)
    with pytest.raises(ValueError, match="persisted"):
        run_research(None, unpersisted, provider, providers_config=_CONFIG)  # type: ignore[arg-type]
