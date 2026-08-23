"""Refresh-token session persistence operations without issuance or rotation logic."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.refresh_tokens import is_refresh_token_hash
from app.db.models.refresh_token_session import RefreshTokenSession


class RefreshTokenSessionRepository:
    """Persistence boundary for hashed refresh-token sessions using an injected session."""

    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        replaced_by_session_id: UUID | None = None,
    ) -> RefreshTokenSession:
        """Stage a digest-only session and flush database constraints without committing."""
        if not is_refresh_token_hash(token_hash):
            raise ValueError("token_hash must be a lowercase SHA-256 hex digest")
        if expires_at.tzinfo is None or expires_at.utcoffset() is None:
            raise ValueError("expires_at must be timezone-aware")
        token_session = RefreshTokenSession(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            replaced_by_session_id=replaced_by_session_id,
        )
        self._session.add(token_session)
        self._session.flush()
        return token_session

    def get_by_token_hash(self, token_hash: str) -> RefreshTokenSession | None:
        """Return a token session by digest, if present."""
        if not is_refresh_token_hash(token_hash):
            return None
        statement = select(RefreshTokenSession).where(RefreshTokenSession.token_hash == token_hash)
        return self._session.scalar(statement)

    def get_active_by_token_hash(self, token_hash: str) -> RefreshTokenSession | None:
        """Return a non-revoked, non-expired session by digest, if present."""
        if not is_refresh_token_hash(token_hash):
            return None
        statement = select(RefreshTokenSession).where(
            RefreshTokenSession.token_hash == token_hash,
            RefreshTokenSession.revoked_at.is_(None),
            RefreshTokenSession.expires_at > func.now(),
        )
        return self._session.scalar(statement)

    def get_active_by_token_hash_for_update(self, token_hash: str) -> RefreshTokenSession | None:
        """Lock an active session row so concurrent rotation attempts serialize in PostgreSQL."""
        if not is_refresh_token_hash(token_hash):
            return None
        statement = (
            select(RefreshTokenSession)
            .where(
                RefreshTokenSession.token_hash == token_hash,
                RefreshTokenSession.revoked_at.is_(None),
                RefreshTokenSession.expires_at > func.now(),
            )
            .with_for_update()
        )
        return self._session.scalar(statement)

    def revoke_and_replace(
        self,
        token_session: RefreshTokenSession,
        replacement_session: RefreshTokenSession,
    ) -> RefreshTokenSession:
        """Revoke one locked session and link it to its staged replacement without committing."""
        token_session.revoked_at = datetime.now(timezone.utc)
        token_session.replaced_by_session_id = replacement_session.id
        self._session.flush()
        return token_session

    def revoke(self, token_session: RefreshTokenSession) -> RefreshTokenSession:
        """Mark one session revoked without committing the enclosing transaction."""
        if token_session.revoked_at is None:
            token_session.revoked_at = datetime.now(timezone.utc)
            self._session.flush()
        return token_session
