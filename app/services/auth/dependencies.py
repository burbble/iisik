from __future__ import annotations

import os
from functools import lru_cache

from .service import AuthService
from .sessions import InMemorySessionStore, RedisSessionStore
from .tokens import JWTManager


@lru_cache(maxsize=1)
def get_auth_service() -> AuthService:
    backend = os.getenv(
        "LAB7_SESSION_BACKEND",
        os.getenv("LAB6_SESSION_BACKEND", os.getenv("LAB5_SESSION_BACKEND", "redis")),
    ).lower()
    if backend == "memory":
        sessions = InMemorySessionStore()
    else:
        sessions = RedisSessionStore(os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    secret = os.getenv("JWT_SECRET", "lab6-development-secret-change-me")
    ttl = int(os.getenv("JWT_TTL_SECONDS", "3600"))
    return AuthService(sessions=sessions, tokens=JWTManager(secret, ttl_seconds=ttl))
