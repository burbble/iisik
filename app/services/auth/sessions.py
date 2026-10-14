from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    user_id: str
    email: str
    roles: tuple[str, ...]
    expires_at: datetime


class SessionStore(Protocol):
    def save(self, record: SessionRecord, ttl_seconds: int) -> None: ...
    def get(self, session_id: str) -> SessionRecord | None: ...
    def delete(self, session_id: str) -> None: ...


class InMemorySessionStore:
    """Test/development double. Production mode uses RedisSessionStore."""

    def __init__(self):
        self._items: dict[str, SessionRecord] = {}

    def save(self, record: SessionRecord, ttl_seconds: int) -> None:
        self._items[record.session_id] = record

    def get(self, session_id: str) -> SessionRecord | None:
        row = self._items.get(session_id)
        if row is None:
            return None
        if row.expires_at <= datetime.now(timezone.utc):
            self._items.pop(session_id, None)
            return None
        return row

    def delete(self, session_id: str) -> None:
        self._items.pop(session_id, None)


class RedisSessionStore:
    KEY_PREFIX = "profitability:session:"

    def __init__(self, redis_url: str):
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("Package 'redis' is required for RedisSessionStore") from exc
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def _key(self, session_id: str) -> str:
        return f"{self.KEY_PREFIX}{session_id}"

    def save(self, record: SessionRecord, ttl_seconds: int) -> None:
        payload = json.dumps(
            {
                "session_id": record.session_id,
                "user_id": record.user_id,
                "email": record.email,
                "roles": list(record.roles),
                "expires_at": record.expires_at.isoformat(),
            },
            ensure_ascii=False,
        )
        self._client.set(self._key(record.session_id), payload, ex=ttl_seconds)

    def get(self, session_id: str) -> SessionRecord | None:
        payload = self._client.get(self._key(session_id))
        if payload is None:
            return None
        data = json.loads(payload)
        return SessionRecord(
            session_id=data["session_id"],
            user_id=data["user_id"],
            email=data["email"],
            roles=tuple(data.get("roles", [])),
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )

    def delete(self, session_id: str) -> None:
        self._client.delete(self._key(session_id))
