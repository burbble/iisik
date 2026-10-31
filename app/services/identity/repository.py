from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from .database import SessionLocal
from .models import Role, User, UserRole


class IdentityRepository:
    def get_user(self, user_id: str) -> User | None:
        with SessionLocal() as session:
            return session.scalar(select(User).where(User.user_id == user_id))

    def get_user_by_email(self, email: str) -> User | None:
        with SessionLocal() as session:
            return session.scalar(
                select(User).where(User.email == email.lower().strip())
            )

    def list_roles(self, user_id: str) -> list[str]:
        with SessionLocal() as session:
            stmt = (
                select(Role.name)
                .join(UserRole, UserRole.role_id == Role.role_id)
                .where(UserRole.user_id == user_id)
                .order_by(Role.name)
            )
            return list(session.scalars(stmt).all())

    def get_role_by_name(self, name: str) -> Role | None:
        with SessionLocal() as session:
            return session.scalar(select(Role).where(Role.name == name))

    def ensure_role(self, name: str, description: str | None = None) -> Role:
        existing = self.get_role_by_name(name)
        if existing is not None:
            return existing
        role = Role(role_id=str(uuid4()), name=name, description=description)
        with SessionLocal.begin() as session:
            session.add(role)
        return role

    def create_user(
        self, email: str, password_hash: str, role_name: str = "PENDING"
    ) -> User:
        now = datetime.now()
        role = self.ensure_role(role_name)
        user = User(
            user_id=str(uuid4()),
            email=email.lower().strip(),
            password_hash=password_hash,
            status="ACTIVE",
            created_at=now,
        )
        with SessionLocal.begin() as session:
            session.add(user)
            session.flush()
            session.add(
                UserRole(user_id=user.user_id, role_id=role.role_id, assigned_at=now)
            )
        return user

    def assign_role(self, user_id: str, role_name: str) -> None:
        role = self.ensure_role(role_name)
        with SessionLocal.begin() as session:
            existing = session.scalar(
                select(UserRole).where(
                    UserRole.user_id == user_id,
                    UserRole.role_id == role.role_id,
                )
            )
            if existing is None:
                session.add(
                    UserRole(
                        user_id=user_id,
                        role_id=role.role_id,
                        assigned_at=datetime.now(),
                    )
                )
