from app.config import sqlite_url
from app.shared.database import make_engine, make_session_factory
from .models import Base

engine = make_engine(sqlite_url("costing.db"))
SessionLocal = make_session_factory(engine)


def init_db() -> None:
    Base.metadata.create_all(engine)
