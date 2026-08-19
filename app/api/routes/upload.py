import logging

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, Field
from app.pipelines.ingest_pipeline import ingest_pipeline
from app.utils.file_handler import get_file_type, remove_upload_file, save_upload_file
from app.models.memory import MemoryResponse
from app.services.link_service import link_service


logger = logging.getLogger(__name__)

router = APIRouter()


# ── Text Input Model ──
class TextUploadRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    text:  str = Field(..., min_length=1, max_length=100_000)

class LinkUploadRequest(BaseModel):
    url: str = Field(..., min_length=5, max_length=2_048)


@router.post("/upload/link", response_model=MemoryResponse)
async def upload_link(request: LinkUploadRequest):
    """
    يستقبل لينك (يوتيوب، تيك توك، أو أي موقع) ويحفظه كـ memory.
    """
    link_service.validate_url(request.url)
    return ingest_pipeline.process_link(url=request.url)


@router.post("/upload", response_model=MemoryResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    يستقبل ملف من المستخدم ويحفظه كـ memory.
    Supported: PNG, JPG, JPEG, PDF
    """

    get_file_type(file.content_type)
    _, file_path, file_type = await save_upload_file(file)

    try:
        return ingest_pipeline.process(
            file_path=file_path,
            file_name=file.filename or "upload",
            file_type=file_type,
            file_size=file.size or 0,
        )
    except Exception:
        remove_upload_file(file_path)
        logger.exception("Upload ingestion failed")
        raise


@router.post("/upload/text", response_model=MemoryResponse)
async def upload_text(request: TextUploadRequest):
    """
    يستقبل نص مباشر من المستخدم ويحفظه كـ memory.
    بيتخطى الـ OCR خالص — النص جاهز.
    """
    return ingest_pipeline.process_text(text=request.text, title=request.title)
