"""SQLite engine and session management (SQLModel)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from lead_radar import models  # noqa: F401  (registers tables on SQLModel.metadata)
from lead_radar.settings import get_settings


def get_engine(db_path: Path | None = None) -> Engine:
    path = db_path or get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", echo=False)


def init_db(db_path: Path | None = None) -> None:
    engine = get_engine(db_path)
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session(db_path: Path | None = None) -> Iterator[Session]:
    engine = get_engine(db_path)
    with Session(engine) as session:
        yield session
