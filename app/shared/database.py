from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


def make_engine(url: str) -> Engine:
    return create_engine(
        url,
        future=True,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )


def make_session_factory(engine: Engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
