from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel, Field
from app.pipelines.ingest_pipeline import ingest_pipeline
from app.utils.file_handler import save_upload_file, get_file_type
from app.models.memory import MemoryResponse
from app.core.exceptions import (
    OCRFailedException,
    UnsupportedFileTypeException,
    StorageException
)

router = APIRouter()


# ── Text Input Model ──
class TextUploadRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    text:  str = Field(..., min_length=1)


@router.post("/upload", response_model=MemoryResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    يستقبل ملف من المستخدم ويحفظه كـ memory.
    Supported: PNG, JPG, JPEG, PDF
    """

    try:
        file_type = get_file_type(file.content_type)
    except UnsupportedFileTypeException as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        document_id, file_path, file_type = await save_upload_file(file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل حفظ الملف: {str(e)}")

    try:
        result = ingest_pipeline.process(
            file_path=file_path,
            file_name=file.filename,
            file_type=file_type,
            file_size=file.size or 0,
        )
        return result

    except OCRFailedException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except StorageException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/text", response_model=MemoryResponse)
async def upload_text(request: TextUploadRequest):
    """
    يستقبل نص مباشر من المستخدم ويحفظه كـ memory.
    بيتخطى الـ OCR خالص — النص جاهز.
    """
    try:
        result = ingest_pipeline.process_text(
            text=request.text,
            title=request.title,
        )
        return result

    except StorageException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))