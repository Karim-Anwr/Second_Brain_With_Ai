from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class FileType(str, Enum):
    IMAGE = "image"
    PDF   = "pdf"

class DocumentChunk(BaseModel):
    """chunk واحد من الـ document"""
    chunk_id:    str
    document_id: str
    text:        str
    chunk_index: int
    file_name:   str
    file_type:   FileType
    file_path:   str
    upload_date: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )

class DocumentResponse(BaseModel):
    """الـ response اللي بترجعه للمستخدم بعد الـ upload"""
    document_id:    str
    file_name:      str
    file_type:      FileType
    chunks_stored:  int
    status:         str = "success"