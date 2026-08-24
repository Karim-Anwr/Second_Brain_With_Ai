"""Compositional owner-aware delivery of files backed by logical memories."""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import DocumentNotFoundException, ResourceNotFoundException
from app.services.ownership_service import OwnershipMismatchError, OwnershipResourceNotFoundError
from app.services.storage_service import storage_service
from app.utils.file_handler import resolve_upload_file_owned


_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


@dataclass(frozen=True)
class OwnedMemoryFile:
    path: Path
    media_type: str
    download_name: str


class FileDeliveryService:
    """Resolve a file only from an already-owned logical memory."""

    def resolve_owned_memory_file(self, db: Session, owner_user_id: UUID, memory_id: str) -> OwnedMemoryFile:
        try:
            chunks = storage_service.get_memory_owned(db, owner_user_id, memory_id)
            if not chunks:
                raise ValueError("memory has no chunks")
            metadata = chunks[0].get("metadata", {})
            file_id = metadata.get("file_id")
            file_path = metadata.get("file_path")
            if not isinstance(file_id, str) or not isinstance(file_path, str):
                raise ValueError("memory has no backing upload")
            UUID(file_id)
            extension = Path(file_path).suffix.lower()
            media_type = _MEDIA_TYPES.get(extension)
            if media_type is None:
                raise ValueError("unsupported backing file")
            path = resolve_upload_file_owned(db, owner_user_id, file_id, extension)
            if Path(file_path).resolve() != path:
                raise ValueError("backing upload relationship is invalid")
            return OwnedMemoryFile(path=path, media_type=media_type, download_name=f"{memory_id}{extension}")
        except (
            DocumentNotFoundException,
            FileNotFoundError,
            OwnershipMismatchError,
            OwnershipResourceNotFoundError,
            ValueError,
        ):
            raise ResourceNotFoundException() from None


file_delivery_service = FileDeliveryService()
