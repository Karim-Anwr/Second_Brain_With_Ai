"""Registration/login orchestration with one transaction per token-issuance flow."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, verify_password
from app.auth.refresh_tokens import hash_refresh_token
from app.auth.tokens import create_access_token, generate_refresh_token, refresh_token_lifetime
from app.core.exceptions import AuthenticationFailedException, RegistrationFailedException
from app.db.repositories.refresh_token_session import RefreshTokenSessionRepository
from app.db.repositories.user import UserRepository
from app.schemas.auth import AuthTokenResponse, LoginRequest, RegistrationRequest
from app.schemas.user import UserCreate


class AuthService:
    """Issue initial token pairs while preserving one service-owned transaction boundary."""

    def __init__(self, session: Session):
        self._session = session
        self._users = UserRepository(session)
        self._refresh_sessions = RefreshTokenSessionRepository(session)

    def register(self, request: RegistrationRequest) -> AuthTokenResponse:
        """Create a user and initial refresh session atomically, then return token pair."""
        try:
            display_name = request.display_name or request.email.split("@", maxsplit=1)[0]
            user = self._users.create(
                UserCreate(
                    email=request.email,
                    password_hash=hash_password(request.password),
                    display_name=display_name,
                )
            )
        except IntegrityError as exc:
            self._session.rollback()
            raise RegistrationFailedException() from exc

        try:
            response = self._issue_initial_tokens(user.id)
            self._session.commit()
            return response
        except Exception:
            self._session.rollback()
            raise

    def login(self, request: LoginRequest) -> AuthTokenResponse:
        """Authenticate with generic failures and persist one initial refresh session."""
        user = self._users.get_by_email(request.email)
        if user is None:
            # Spend comparable Argon2 work for unknown accounts so the generic
            # client-facing failure is not trivially distinguishable by timing.
            hash_password(request.password)
            raise AuthenticationFailedException()
        password_is_valid = verify_password(request.password, user.password_hash)
        if not user.is_active or not password_is_valid:
            raise AuthenticationFailedException()
        try:
            response = self._issue_initial_tokens(user.id)
            self._session.commit()
            return response
        except Exception:
            self._session.rollback()
            raise

    def _issue_initial_tokens(self, user_id) -> AuthTokenResponse:
        access_token = create_access_token(user_id)
        raw_refresh_token = generate_refresh_token()
        expires_at = datetime.now(timezone.utc) + refresh_token_lifetime()
        self._refresh_sessions.create(
            user_id=user_id,
            token_hash=hash_refresh_token(raw_refresh_token),
            expires_at=expires_at,
        )
        expires_in = max(0, int((access_token.expires_at - datetime.now(timezone.utc)).total_seconds()))
        return AuthTokenResponse(
            access_token=access_token.value,
            refresh_token=raw_refresh_token,
            expires_at=access_token.expires_at,
            expires_in=expires_in,
        )
