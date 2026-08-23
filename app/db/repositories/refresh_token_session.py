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

    def get_by_token_hash_for_update(self, token_hash: str) -> RefreshTokenSession | None:
        """Lock any token-session state for an atomic refresh or reuse decision."""
        if not is_refresh_token_hash(token_hash):
            return None
        statement = (
            select(RefreshTokenSession)
            .where(RefreshTokenSession.token_hash == token_hash)
            .with_for_update()
        )
        return self._session.scalar(statement)

    def get_replacement_lineage_for_update(
        self, token_session: RefreshTokenSession
    ) -> list[RefreshTokenSession]:
        """Return a locked replacement chain rooted at ``token_session``.

        The replacement column has a uniqueness constraint, so each session can
        have at most one successor. The traversal guards corruption explicitly
        rather than risking cross-user revocation or an infinite cycle.
        """
        lineage = [token_session]
        visited_ids = {token_session.id}
        replacement_session_id = token_session.replaced_by_session_id

        while replacement_session_id is not None:
            if replacement_session_id in visited_ids:
                raise RuntimeError("refresh token replacement lineage contains a cycle")
            statement = (
                select(RefreshTokenSession)
                .where(RefreshTokenSession.id == replacement_session_id)
                .with_for_update()
            )
            replacement = self._session.scalar(statement)
            if replacement is None:
                raise RuntimeError("refresh token replacement lineage is incomplete")
            if replacement.user_id != token_session.user_id:
                raise RuntimeError("refresh token replacement lineage crosses users")
            lineage.append(replacement)
            visited_ids.add(replacement.id)
            replacement_session_id = replacement.replaced_by_session_id

        return lineage

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

    def revoke_replacement_lineage(
        self, lineage: list[RefreshTokenSession]
    ) -> list[RefreshTokenSession]:
        """Revoke an already-locked replacement lineage with one non-committing flush."""
        revoked_at = datetime.now(timezone.utc)
        for token_session in lineage:
            if token_session.revoked_at is None:
                token_session.revoked_at = revoked_at
        self._session.flush()
        return lineage
