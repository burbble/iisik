from __future__ import annotations

from dataclasses import dataclass
import os

import httpx

from app.shared.errors import AuthenticationError, ConflictError, ValidationError
from app.shared.security import Actor


@dataclass(frozen=True)
class LoginPayload:
    access_token: str
    token_type: str
    expires_at: str
    user_id: str
    email: str
    roles: tuple[str, ...]


class AuthClient:
    """REST client used by GraphQL Gateway to delegate security to Auth Service."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("AUTH_SERVICE_URL", "http://127.0.0.1:8001")).rstrip("/")

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            return httpx.request(method, f"{self.base_url}{path}", timeout=3.0, **kwargs)
        except httpx.HTTPError as exc:
            raise AuthenticationError("Auth Service is unavailable") from exc

    def register(self, email: str, password: str) -> Actor:
        response = self._request("POST", "/auth/register", json={"email": email, "password": password})
        if response.status_code == 409:
            raise ConflictError(response.json().get("detail", "User already exists"))
        if response.status_code == 422:
            raise ValidationError(response.json().get("detail", "Invalid registration data"))
        if response.status_code != 201:
            raise AuthenticationError("Registration failed")
        data = response.json()
        return Actor(data["id"], data["email"], tuple(data["roles"]), session_id="")

    def login(self, email: str, password: str) -> LoginPayload:
        response = self._request("POST", "/auth/login", json={"email": email, "password": password})
        if response.status_code != 200:
            raise AuthenticationError("Invalid credentials")
        data = response.json()
        user = data["user"]
        return LoginPayload(
            access_token=data["access_token"],
            token_type=data["token_type"],
            expires_at=data["expires_at"],
            user_id=user["id"],
            email=user["email"],
            roles=tuple(user["roles"]),
        )

    def verify(self, token: str) -> Actor:
        response = self._request(
            "GET",
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code != 200:
            raise AuthenticationError("JWT or active session is invalid")
        data = response.json()
        return Actor(
            user_id=data["id"],
            email=data["email"],
            roles=tuple(data["roles"]),
            session_id="verified-by-auth-service",
        )

    def logout(self, token: str) -> None:
        response = self._request(
            "POST",
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code not in {200, 204}:
            raise AuthenticationError("Logout failed")
