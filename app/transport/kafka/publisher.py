from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_MAX_ATTEMPTS,
    KAFKA_RETRY_BACKOFF_SECONDS,
    KAFKA_TOPIC,
)
from app.shared.logging_config import get_logger
from .events import EventEnvelope

logger = get_logger("transport.kafka.publisher")


class EventPublisher:
    def publish(self, event: EventEnvelope) -> None:
        raise NotImplementedError


@dataclass
class InMemoryEventPublisher(EventPublisher):
    events: list[EventEnvelope] = field(default_factory=list)

    def publish(self, event: EventEnvelope) -> None:
        self.events.append(event)


class KafkaEventPublisher(EventPublisher):
    def __init__(
        self,
        bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
        topic: str = KAFKA_TOPIC,
        max_attempts: int = KAFKA_MAX_ATTEMPTS,
        backoff_seconds: float = KAFKA_RETRY_BACKOFF_SECONDS,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self._producer = None

    def _get_producer(self):
        if self._producer is None:
            try:
                from kafka import KafkaProducer
            except ImportError as exc:
                raise RuntimeError(
                    "kafka-python is required for Kafka runtime"
                ) from exc
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers.split(","),
                acks="all",
                retries=0,
                linger_ms=5,
                request_timeout_ms=3000,
                max_block_ms=3000,
            )
        return self._producer

    def _send_once(self, event: EventEnvelope) -> None:
        future = self._get_producer().send(
            self.topic,
            key=event.eventType.encode("utf-8"),
            value=event.to_bytes(),
        )
        future.get(timeout=5)

    def publish(self, event: EventEnvelope) -> None:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                self._send_once(event)
                logger.info(
                    "Kafka event published",
                    extra={
                        "event_type": event.eventType,
                        "correlation_id": event.correlationId,
                        "attempt": attempt,
                        "operation": self.topic,
                    },
                )
                return
            except Exception as exc:
                last_error = exc
                retrying = attempt < self.max_attempts
                logger.warning(
                    "Kafka publish failed%s" % (", retrying" if retrying else ""),
                    extra={
                        "event_type": event.eventType,
                        "correlation_id": event.correlationId,
                        "attempt": attempt,
                        "operation": self.topic,
                        "error_type": type(exc).__name__,
                    },
                )
                if not retrying:
                    break
                time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))
        assert last_error is not None
        raise RuntimeError(
            f"Kafka publish failed after {self.max_attempts} attempts"
        ) from last_error

    def close(self):
        if self._producer is not None:
            self._producer.flush(timeout=10)
            self._producer.close()
