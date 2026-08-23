"""Ownership control-plane persistence without authorization or transaction ownership."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.owned_resource import OwnedResource, OwnedResourceKind


class OwnedResourceRepository:
    """Stage and query immutable logical-resource ownership records."""

    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        *,
        owner_user_id: UUID,
        resource_kind: OwnedResourceKind | str,
        resource_id: str,
    ) -> OwnedResource:
        """Stage one ownership record and flush database constraints without committing."""
        resource = OwnedResource(
            owner_user_id=owner_user_id,
            resource_kind=resource_kind,
            resource_id=resource_id,
        )
        self._session.add(resource)
        self._session.flush()
        return resource

    def get_by_resource(self, *, resource_kind: OwnedResourceKind | str, resource_id: str) -> OwnedResource | None:
        """Return the record for a logical identity without collapsing owner distinctions."""
        kind = resource_kind.value if isinstance(resource_kind, OwnedResourceKind) else resource_kind
        statement = select(OwnedResource).where(
            OwnedResource.resource_kind == kind,
            OwnedResource.resource_id == resource_id,
        )
        return self._session.scalar(statement)

    def get_by_owner_and_resource(
        self,
        *,
        owner_user_id: UUID,
        resource_kind: OwnedResourceKind | str,
        resource_id: str,
    ) -> OwnedResource | None:
        """Return the record only when the requested owner matches the logical identity."""
        kind = resource_kind.value if isinstance(resource_kind, OwnedResourceKind) else resource_kind
        statement = select(OwnedResource).where(
            OwnedResource.owner_user_id == owner_user_id,
            OwnedResource.resource_kind == kind,
            OwnedResource.resource_id == resource_id,
        )
        return self._session.scalar(statement)
