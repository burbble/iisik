from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Actor:
    user_id: str
    email: str
    roles: tuple[str, ...]
    session_id: str

    def has_role(self, *roles: str) -> bool:
        current = set(self.roles)
        return "ADMIN" in current or bool(current.intersection(roles))
