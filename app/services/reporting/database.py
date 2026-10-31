from app.config import sqlite_url
from app.shared.database import make_engine, make_session_factory
from .models import Base

engine = make_engine(sqlite_url("reporting.db"))
SessionLocal = make_session_factory(engine)


def init_db() -> None:
    Base.metadata.create_all(engine)

    from sqlalchemy import inspect, text

    if "cost_version" not in {
        c["name"] for c in inspect(engine).get_columns("profitability_read_model")
    }:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE profitability_read_model ADD COLUMN cost_version INTEGER NOT NULL DEFAULT 0"
                )
            )
