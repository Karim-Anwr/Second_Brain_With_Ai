"""Thin Phase 2.3B registration and login routes only."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.api import error_responses
from app.schemas.auth import AuthTokenResponse, LoginRequest, RefreshTokenRequest, RegistrationRequest
from app.services.auth_service import AuthService


router = APIRouter()


@router.post(
    "/auth/register",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409, 422, 500),
)
def register(request: RegistrationRequest, session: Annotated[Session, Depends(get_db)]) -> AuthTokenResponse:
    return AuthService(session).register(request)


@router.post("/auth/login", response_model=AuthTokenResponse, responses=error_responses(401, 422, 500))
def login(request: LoginRequest, session: Annotated[Session, Depends(get_db)]) -> AuthTokenResponse:
    return AuthService(session).login(request)


@router.post("/auth/refresh", response_model=AuthTokenResponse, responses=error_responses(401, 422, 500))
def refresh(request: RefreshTokenRequest, session: Annotated[Session, Depends(get_db)]) -> AuthTokenResponse:
    return AuthService(session).refresh(request)
