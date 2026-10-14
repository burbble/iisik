from dataclasses import dataclass

from .repository import IdentityRepository


@dataclass(frozen=True)
class UserDTO:
    id: str
    email: str
    status: str
    roles: tuple[str, ...] = ()


class IdentityService:
    def __init__(self, repository: IdentityRepository | None = None):
        self.repository = repository or IdentityRepository()

    def get_user(self, user_id: str) -> UserDTO | None:
        row = self.repository.get_user(user_id)
        if row is None:
            return None
        return UserDTO(
            id=row.user_id,
            email=row.email,
            status=row.status,
            roles=tuple(self.repository.list_roles(row.user_id)),
        )
