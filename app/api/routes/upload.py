import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.auth.current_user import CurrentUser
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.pipelines.ingest_pipeline import ingest_pipeline
from app.utils.file_handler import (
    get_file_type,
    remove_owned_upload_file,
    save_upload_file_owned,
)
from app.models.memory import MemoryResponse
from app.models.api import error_responses
from app.services.link_service import link_service


logger = logging.getLogger(__name__)

router = APIRouter()


# ── Text Input Model ──
class TextUploadRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    text:  str = Field(..., min_length=1, max_length=100_000)

class LinkUploadRequest(BaseModel):
    url: str = Field(..., min_length=5, max_length=2_048)


@router.post("/upload/link", response_model=MemoryResponse, responses=error_responses(400, 401, 422, 500, 503))
async def upload_link(
    request: LinkUploadRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    يستقبل لينك (يوتيوب، تيك توك، أو أي موقع) ويحفظه كـ memory.
    """
    link_service.validate_url(request.url)
    result = await ingest_pipeline.process_link_owned(db, current_user.id, request.url)
    db.commit()
    return result


@router.post("/upload", response_model=MemoryResponse, responses=error_responses(401, 413, 415, 422, 500, 503))
async def upload_file(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    """
    يستقبل ملف من المستخدم ويحفظه كـ memory.
    Supported: PNG, JPG, JPEG, PDF
    """

    get_file_type(file.content_type)
    file_id, file_path, file_type = await save_upload_file_owned(db, current_user.id, file)

    try:
        result = ingest_pipeline.process_owned(
            db=db,
            owner_user_id=current_user.id,
            file_path=file_path,
            file_name=file.filename or "upload",
            file_type=file_type,
            file_id=file_id,
            file_size=file.size or 0,
        )
        db.commit()
        return result
    except Exception:
        remove_owned_upload_file(file_path)
        logger.exception("Upload ingestion failed")
        raise


@router.post("/upload/text", response_model=MemoryResponse, responses=error_responses(401, 422, 500, 503))
async def upload_text(
    request: TextUploadRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    يستقبل نص مباشر من المستخدم ويحفظه كـ memory.
    بيتخطى الـ OCR خالص — النص جاهز.
    """
    result = ingest_pipeline.process_text_owned(db, current_user.id, request.text, request.title)
    db.commit()
    return result
