from __future__ import annotations

import threading
import time
from collections.abc import Callable

from app.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_DEAD_LETTER_TOPIC,
    KAFKA_MAX_ATTEMPTS,
    KAFKA_RETRY_BACKOFF_SECONDS,
    KAFKA_TOPIC,
)
from app.shared.logging_config import get_logger
from .events import EventEnvelope
from .publisher import KafkaEventPublisher

logger = get_logger("transport.kafka.consumer")


class KafkaEventConsumer:
    def __init__(
        self,
        group_id: str,
        handlers: dict[str, Callable[[EventEnvelope], None]],
        bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
        topic: str = KAFKA_TOPIC,
        max_attempts: int = KAFKA_MAX_ATTEMPTS,
        backoff_seconds: float = KAFKA_RETRY_BACKOFF_SECONDS,
        dead_letter_topic: str = KAFKA_DEAD_LETTER_TOPIC,
    ):
        self.group_id = group_id
        self.handlers = handlers
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self.dead_letter_topic = dead_letter_topic
        self._stop = threading.Event()
        self._dead_letter = None

    def _process(self, event: EventEnvelope) -> bool:
        handler = self.handlers.get(event.eventType)
        if handler is None:
            logger.info(
                "Kafka event ignored: no handler",
                extra={"event_type": event.eventType, "correlation_id": event.correlationId, "operation": self.group_id},
            )
            return True
        for attempt in range(1, self.max_attempts + 1):
            try:
                handler(event)
                logger.info(
                    "Kafka event processed",
                    extra={
                        "event_type": event.eventType,
                        "correlation_id": event.correlationId,
                        "attempt": attempt,
                        "operation": self.group_id,
                    },
                )
                return True
            except Exception as exc:
                retrying = attempt < self.max_attempts
                logger.warning(
                    "Kafka handler failed%s" % (", retrying" if retrying else ""),
                    extra={
                        "event_type": event.eventType,
                        "correlation_id": event.correlationId,
                        "attempt": attempt,
                        "operation": self.group_id,
                        "error_type": type(exc).__name__,
                    },
                )
                if retrying:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))
                    continue
                self._send_to_dead_letter(event, exc)
                return False
        return False

    def _send_to_dead_letter(self, event: EventEnvelope, error: Exception) -> None:
        if self._dead_letter is None:
            self._dead_letter = KafkaEventPublisher(
                bootstrap_servers=self.bootstrap_servers,
                topic=self.dead_letter_topic,
            )
        failed = EventEnvelope.create(
            "KafkaMessageFailed",
            "kafka-consumer",
            {
                "originalEventType": event.eventType,
                "originalEventId": event.eventId,
                "originalPayload": event.payload,
                "consumerGroup": self.group_id,
                "errorType": type(error).__name__,
                "errorMessage": str(error),
            },
            correlation_id=event.correlationId,
        )
        try:
            self._dead_letter.publish(failed)
            logger.error(
                "Kafka event moved to dead-letter topic",
                extra={"event_type": event.eventType, "correlation_id": event.correlationId, "operation": self.dead_letter_topic},
            )
        except Exception:
            logger.exception(
                "Failed to publish dead-letter event",
                extra={"event_type": event.eventType, "correlation_id": event.correlationId, "operation": self.dead_letter_topic},
            )

    def run_forever(self):
        try:
            from kafka import KafkaConsumer
        except ImportError as exc:
            raise RuntimeError("kafka-python is required for Kafka runtime") from exc
        consumer = KafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers.split(","),
            group_id=self.group_id,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            value_deserializer=lambda raw: EventEnvelope.from_bytes(raw),
        )
        try:
            for record in consumer:
                if self._stop.is_set():
                    break
                try:
                    event = record.value
                    self._process(event)
                except Exception as exc:
                    logger.exception("Kafka record deserialization/processing failed", extra={"operation": self.group_id, "error_type": type(exc).__name__})
                finally:
                    # Commit after success or after DLQ handoff so a poison message does not block the partition forever.
                    consumer.commit()
        finally:
            consumer.close()
            if self._dead_letter is not None:
                self._dead_letter.close()

    def start_in_thread(self, name: str | None = None):
        thread = threading.Thread(target=self.run_forever, name=name or self.group_id, daemon=True)
        thread.start()
        return thread

    def stop(self):
        self._stop.set()
