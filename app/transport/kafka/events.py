from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class EventEnvelope:
    eventId: str
    eventType: str
    occurredAt: str
    producer: str
    schemaVersion: int
    correlationId: str
    payload: dict

    @classmethod
    def create(
        cls,
        event_type: str,
        producer: str,
        payload: dict,
        correlation_id: str | None = None,
    ):
        return cls(
            eventId=str(uuid4()),
            eventType=event_type,
            occurredAt=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            producer=producer,
            schemaVersion=1,
            correlationId=correlation_id or str(uuid4()),
            payload=payload,
        )

    def to_dict(self) -> dict:
        return {
            "eventId": self.eventId,
            "eventType": self.eventType,
            "occurredAt": self.occurredAt,
            "producer": self.producer,
            "schemaVersion": self.schemaVersion,
            "correlationId": self.correlationId,
            "payload": self.payload,
        }

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), ensure_ascii=False).encode("utf-8")

    @classmethod
    def from_bytes(cls, raw: bytes):
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("payload"), dict):
            raise ValueError("Event payload must be an object")
        for key in ["eventId", "eventType", "occurredAt", "producer", "correlationId"]:
            if not isinstance(data.get(key), str) or not data[key]:
                raise ValueError(f"Invalid event field: {key}")
        if data.get("schemaVersion") != 1:
            raise ValueError("Unsupported event schema version")
        return cls(**data)
