from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlmodel import Session

from lead_radar.db import get_engine, init_db
from lead_radar.models.account import Account
from lead_radar.models.enums import AccountStatus, ARRConfidence


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def session(db_path: Path) -> Iterator[Session]:
    init_db(db_path)
    engine = get_engine(db_path)
    with Session(engine) as s:
        yield s


def make_account(
    session: Session,
    *,
    domain: str = "example-co.example",
    company_name: str = "Example Co",
    headquarters_country: str = "US",
    employee_count: int = 100,
    reported_revenue_usd: float | None = 50_000_000,
    company_type: str = "b2b_saas",
    industry: str = "B2B SaaS",
    status: AccountStatus = AccountStatus.PRELIMINARY_QUALIFIED,
    arr_confidence: ARRConfidence = ARRConfidence.UNKNOWN,
) -> Account:
    account = Account(
        domain=domain,
        company_name=company_name,
        headquarters_country=headquarters_country,
        employee_count=employee_count,
        reported_revenue_usd=reported_revenue_usd,
        company_type=company_type,
        industry=industry,
        status=status,
        arr_confidence=arr_confidence,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account
