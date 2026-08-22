"""User persistence access without authentication or HTTP concerns."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.email import canonicalize_email
from app.db.models.user import User
from app.schemas.user import UserCreate


class UserRepository:
    """Create and query users through an injected SQLAlchemy session."""

    def __init__(self, session: Session):
        self._session = session

    def create(self, user_input: UserCreate) -> User:
        """Stage a new canonicalized user and flush database constraints."""
        user = User(
            email=canonicalize_email(user_input.email),
            password_hash=user_input.password_hash,
            display_name=user_input.display_name,
            is_active=user_input.is_active,
        )
        self._session.add(user)
        self._session.flush()
        return user

    def get_by_id(self, user_id: UUID) -> User | None:
        """Return a user by primary key, if present."""
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        """Return a user by a canonicalized email address, if present."""
        statement = select(User).where(User.email == canonicalize_email(email))
        return self._session.scalar(statement)
