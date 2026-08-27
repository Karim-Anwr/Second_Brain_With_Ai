"""Reusable request authentication dependency for future protected routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUser
from app.auth.tokens import AccessTokenVerificationError, verify_access_token
from app.core.exceptions import AuthenticationRequiredException
from app.db.repositories.user import UserRepository
from app.db.session import get_db


_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    session: Annotated[Session, Depends(get_db)],
) -> CurrentUser:
    """Return the active User identity for a verified bearer access token only."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise AuthenticationRequiredException()
    try:
        user_id = verify_access_token(credentials.credentials)
    except AccessTokenVerificationError as exc:
        raise AuthenticationRequiredException() from exc

    user = UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise AuthenticationRequiredException()
    return CurrentUser(id=user.id)
