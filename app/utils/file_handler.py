import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile
from app.core.config import settings
from app.core.exceptions import UnsupportedFileTypeException

SUPPORTED_TYPES = {
    "image/jpeg": "image",
    "image/png":  "image",
    "image/webp": "image",
    "application/pdf": "pdf",
}

def get_file_type(content_type: str) -> str:
    if content_type not in SUPPORTED_TYPES:
        raise UnsupportedFileTypeException(
            f"نوع الملف '{content_type}' مش مدعوم."
            f" الأنواع المدعومة: JPEG, PNG, PDF"
        )
    return SUPPORTED_TYPES[content_type]


async def save_upload_file(upload_file: UploadFile) -> tuple[str, str, str]:
    """
    بيحفظ الملف على الـ disk.
    بيرجع: (document_id, file_path, file_type)
    """
    file_type   = get_file_type(upload_file.content_type)
    document_id = str(uuid.uuid4())  # ID فريد لكل ملف
    extension   = Path(upload_file.filename).suffix
    file_name   = f"{document_id}{extension}"
    file_path   = Path(settings.upload_dir) / file_name

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

    return document_id, str(file_path), file_type

