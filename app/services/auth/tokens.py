from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt


@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    session_id: str
    roles: tuple[str, ...]
    expires_at: datetime


class JWTManager:
    def __init__(
        self, secret: str, ttl_seconds: int = 3600, issuer: str = "profitability-auth"
    ):
        if len(secret) < 24:
            raise ValueError("JWT secret must be at least 24 characters")
        self.secret = secret
        self.ttl_seconds = ttl_seconds
        self.issuer = issuer

    def issue(
        self, user_id: str, session_id: str, roles: tuple[str, ...]
    ) -> tuple[str, datetime]:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.ttl_seconds)
        payload = {
            "sub": user_id,
            "sid": session_id,
            "roles": list(roles),
            "iat": now,
            "exp": expires_at,
            "iss": self.issuer,
            "type": "access",
        }
        token = jwt.encode(payload, self.secret, algorithm="HS256")
        return token, expires_at

    def decode(self, token: str) -> TokenClaims:
        payload = jwt.decode(
            token,
            self.secret,
            algorithms=["HS256"],
            issuer=self.issuer,
            options={"require": ["exp", "iat", "sub", "sid", "iss"]},
        )
        if payload.get("type") != "access":
            raise jwt.InvalidTokenError("Unsupported token type")
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        return TokenClaims(
            user_id=str(payload["sub"]),
            session_id=str(payload["sid"]),
            roles=tuple(str(x) for x in payload.get("roles", [])),
            expires_at=exp,
        )
