"""At-least-once dispatch of events committed with cost calculations."""

import threading
from datetime import datetime
from sqlalchemy import select
from .events import EventEnvelope


class OutboxDispatcher:
    def __init__(self, publisher, domain="costing"):
        from importlib import import_module

        self.SessionLocal = import_module(
            f"app.services.{domain}.database"
        ).SessionLocal
        self.OutboxEvent = import_module(f"app.services.{domain}.models").OutboxEvent
        self.publisher = publisher
        self.lock = threading.Lock()
        self.stop = threading.Event()

    def flush(self):
        SessionLocal, OutboxEvent = self.SessionLocal, self.OutboxEvent
        with self.lock:
            with SessionLocal() as session:
                pending = list(
                    session.scalars(
                        select(OutboxEvent).where(OutboxEvent.published_at.is_(None))
                    )
                )
            for row in pending:
                try:
                    self.publisher.publish(EventEnvelope(**row.envelope))
                except Exception as exc:
                    with SessionLocal.begin() as session:
                        session.get(OutboxEvent, row.event_id).last_error = str(exc)
                    continue
                with SessionLocal.begin() as session:
                    saved = session.get(OutboxEvent, row.event_id)
                    saved.published_at = datetime.now()
                    saved.last_error = None

    def start(self):
        def run():
            while not self.stop.wait(1):
                try:
                    self.flush()
                except Exception:
                    # A DB outage must not terminate recovery; rows remain pending.
                    import logging

                    logging.getLogger(__name__).exception(
                        "Outbox dispatch will be retried"
                    )

        threading.Thread(target=run, name="costing-outbox", daemon=True).start()
