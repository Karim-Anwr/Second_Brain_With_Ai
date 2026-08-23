"""Minimal ownership authority for future owner-scoped resource operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.owned_resource import OwnedResource, OwnedResourceKind
from app.db.repositories.owned_resource import OwnedResourceRepository
from app.db.repositories.user import UserRepository


class OwnershipOwnerNotFoundError(LookupError):
    """Raised when a requested owner does not exist or is inactive."""


class OwnershipResourceNotFoundError(LookupError):
    """Raised when no ownership record exists for a logical resource."""


class OwnershipMismatchError(PermissionError):
    """Raised when a logical resource exists but belongs to another owner."""


class OwnershipService:
    """Authoritative logical-resource ownership checks with explicit owner input."""

    def __init__(self, session: Session):
        self._users = UserRepository(session)
        self._resources = OwnedResourceRepository(session)

    def register_resource(
        self,
        *,
        owner_user_id: UUID,
        resource_kind: OwnedResourceKind | str,
        resource_id: str,
    ) -> OwnedResource:
        """Register a new logical resource for an explicit active owner without committing."""
        self._require_active_owner(owner_user_id)
        return self._resources.create(
            owner_user_id=owner_user_id,
            resource_kind=resource_kind,
            resource_id=resource_id,
        )

    def require_owned_resource(
        self,
        *,
        owner_user_id: UUID,
        resource_kind: OwnedResourceKind | str,
        resource_id: str,
    ) -> OwnedResource:
        """Return an owned resource while preserving missing-versus-mismatch distinction."""
        resource = self._resources.get_by_resource(resource_kind=resource_kind, resource_id=resource_id)
        if resource is None:
            raise OwnershipResourceNotFoundError("ownership record was not found")
        if resource.owner_user_id != owner_user_id:
            raise OwnershipMismatchError("ownership record belongs to another user")
        return resource

    def _require_active_owner(self, owner_user_id: UUID) -> None:
        user = self._users.get_by_id(owner_user_id)
        if user is None or not user.is_active:
            raise OwnershipOwnerNotFoundError("owner does not exist or is inactive")
