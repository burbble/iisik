from app.config import sqlite_url
from app.shared.database import make_engine, make_session_factory
from .models import Base

engine = make_engine(sqlite_url("costing.db"))
SessionLocal = make_session_factory(engine)


def init_db() -> None:
    Base.metadata.create_all(engine)
    from sqlalchemy import inspect, text

    if "source_versions" not in {
        c["name"] for c in inspect(engine).get_columns("cost_calculations")
    }:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE cost_calculations ADD COLUMN source_versions JSON NOT NULL DEFAULT '{}'"
                )
            )

    if "planned_unit_cost" not in {
        c["name"] for c in inspect(engine).get_columns("cost_calculations")
    }:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE cost_calculations ADD COLUMN planned_unit_cost NUMERIC(18,4)"
                )
            )
