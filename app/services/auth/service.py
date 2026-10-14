from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

import jwt

from app.services.identity.repository import IdentityRepository
from app.shared.errors import AuthenticationError, ConflictError, ValidationError
from app.shared.security import Actor

from .passwords import hash_password, verify_password
from .sessions import SessionRecord, SessionStore
from .tokens import JWTManager


@dataclass(frozen=True)
class AuthResult:
    access_token: str
    token_type: str
    expires_at: datetime
    actor: Actor


class AuthService:
    def __init__(
        self,
        sessions: SessionStore,
        tokens: JWTManager,
        identity: IdentityRepository | None = None,
    ):
        self.sessions = sessions
        self.tokens = tokens
        self.identity = identity or IdentityRepository()

    def register(self, email: str, password: str) -> Actor:
        normalized = email.lower().strip()
        if "@" not in normalized:
            raise ValidationError("Invalid email")
        if self.identity.get_user_by_email(normalized) is not None:
            raise ConflictError("User with this email already exists")
        try:
            password_hash = hash_password(password)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        row = self.identity.create_user(normalized, password_hash, role_name="ANALYST")
        return Actor(row.user_id, row.email, ("ANALYST",), session_id="")

    def login(self, email: str, password: str) -> AuthResult:
        row = self.identity.get_user_by_email(email.lower().strip())
        if row is None or row.status != "ACTIVE" or not verify_password(password, row.password_hash):
            raise AuthenticationError("Invalid credentials")
        roles = tuple(self.identity.list_roles(row.user_id))
        session_id = str(uuid4())
        token, expires_at = self.tokens.issue(row.user_id, session_id, roles)
        record = SessionRecord(session_id, row.user_id, row.email, roles, expires_at)
        self.sessions.save(record, self.tokens.ttl_seconds)
        return AuthResult(
            access_token=token,
            token_type="bearer",
            expires_at=expires_at,
            actor=Actor(row.user_id, row.email, roles, session_id),
        )

    def verify(self, token: str) -> Actor:
        try:
            claims = self.tokens.decode(token)
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid or expired JWT") from exc
        session = self.sessions.get(claims.session_id)
        if session is None:
            raise AuthenticationError("Active session was not found")
        if session.user_id != claims.user_id:
            raise AuthenticationError("Session does not belong to token subject")
        user = self.identity.get_user(claims.user_id)
        if user is None or user.status != "ACTIVE":
            raise AuthenticationError("User is not active")
        current_roles = tuple(self.identity.list_roles(user.user_id))
        return Actor(user.user_id, user.email, current_roles, claims.session_id)

    def logout(self, token: str) -> None:
        try:
            claims = self.tokens.decode(token)
        except jwt.PyJWTError:
            return
        self.sessions.delete(claims.session_id)
