import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.owned_resource import OwnedResourceKind
from app.core.exceptions import UnsupportedFileTypeException, UploadTooLargeException
from app.core.legacy_paths import legacy_global_resource_path
from app.services.ownership_service import OwnershipService


SUPPORTED_TYPES = {
    "image/jpeg": ("image", ".jpg"),
    "image/png": ("image", ".png"),
    "image/webp": ("image", ".webp"),
    "application/pdf": ("pdf", ".pdf"),
}


def get_file_type(content_type: str | None) -> str:
    if content_type not in SUPPORTED_TYPES:
        raise UnsupportedFileTypeException("Only JPEG, PNG, WebP, and PDF uploads are supported.")
    return SUPPORTED_TYPES[content_type][0]


def _validate_signature(header: bytes, file_type: str) -> None:
    valid = {
        "image": header.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n"))
        or (header.startswith(b"RIFF") and header[8:12] == b"WEBP"),
        "pdf": header.startswith(b"%PDF-"),
    }
    if not valid.get(file_type, False):
        raise UnsupportedFileTypeException("The uploaded file content does not match its declared type.")


@legacy_global_resource_path("file")
async def save_upload_file(upload_file: UploadFile) -> tuple[str, str, str]:
    """Persist a verified, size-bounded file atomically and return its metadata."""
    content_type = upload_file.content_type
    file_type = get_file_type(content_type)
    extension = SUPPORTED_TYPES[content_type][1]
    document_id = str(uuid.uuid4())
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    temporary_path = upload_dir / f".{document_id}.part"
    final_path = upload_dir / f"{document_id}{extension}"
    total_size = 0

    try:
        with open(temporary_path, "wb") as buffer:
            while chunk := await upload_file.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > settings.max_upload_size_bytes:
                    raise UploadTooLargeException()
                buffer.write(chunk)

        with open(temporary_path, "rb") as uploaded:
            _validate_signature(uploaded.read(16), file_type)

        os.replace(temporary_path, final_path)
        return document_id, str(final_path), file_type
    except Exception:
        temporary_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        raise


@legacy_global_resource_path("file")
def remove_upload_file(file_path: str | Path) -> None:
    """Remove a Phase 1 upload only when it remains under the configured upload root."""
    target = Path(file_path).resolve()
    upload_root = Path(settings.upload_dir).resolve()
    if upload_root == target.parent and target.exists():
        target.unlink()


def remove_owned_upload_file(file_path: str | Path) -> None:
    """Clean up a server-returned owned upload after downstream ingestion fails.

    This is cleanup only; route authorization remains the responsibility of the
    explicit owner-aware persistence and resolution primitives.
    """
    target = Path(file_path).resolve()
    owner_root = Path(settings.upload_dir).resolve() / "owners"
    if owner_root in target.parents and target.exists():
        target.unlink()


def _owner_upload_dir(owner_user_id: str) -> Path:
    """Derive an internal namespace from an authoritative UUID, never a client path."""
    owner_root = Path(settings.upload_dir).resolve() / "owners" / owner_user_id
    owner_root.mkdir(parents=True, exist_ok=True)
    return owner_root


async def save_upload_file_owned(db: Session, owner_user_id, upload_file: UploadFile) -> tuple[str, str, str]:
    """Save a new upload in a server-derived owner namespace after registry staging."""
    content_type = upload_file.content_type
    file_type = get_file_type(content_type)
    extension = SUPPORTED_TYPES[content_type][1]
    file_id = str(uuid.uuid4())
    owner_value = str(owner_user_id)
    owner_dir = _owner_upload_dir(owner_value)
    temporary_path = owner_dir / f".{file_id}.part"
    final_path = owner_dir / f"{file_id}{extension}"
    OwnershipService(db).register_resource(
        owner_user_id=owner_user_id,
        resource_kind=OwnedResourceKind.FILE,
        resource_id=file_id,
    )
    total_size = 0
    try:
        with open(temporary_path, "wb") as buffer:
            while chunk := await upload_file.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > settings.max_upload_size_bytes:
                    raise UploadTooLargeException()
                buffer.write(chunk)
        with open(temporary_path, "rb") as uploaded:
            _validate_signature(uploaded.read(16), file_type)
        os.replace(temporary_path, final_path)
        return file_id, str(final_path), file_type
    except Exception:
        temporary_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        raise


def resolve_upload_file_owned(db: Session, owner_user_id, file_id: str, extension: str) -> Path:
    """Resolve a new file only after owner-scoped registry validation."""
    OwnershipService(db).require_owned_resource(
        owner_user_id=owner_user_id,
        resource_kind=OwnedResourceKind.FILE,
        resource_id=file_id,
    )
    if not extension.startswith(".") or "/" in extension or "\\" in extension:
        raise ValueError("file extension is invalid")
    candidate = (_owner_upload_dir(str(owner_user_id)) / f"{file_id}{extension}").resolve()
    owner_dir = _owner_upload_dir(str(owner_user_id)).resolve()
    if owner_dir not in candidate.parents or not candidate.exists():
        raise FileNotFoundError("owned file was not found")
    return candidate
