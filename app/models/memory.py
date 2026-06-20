from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class FileType(str, Enum):
    IMAGE = "image"
    PDF   = "pdf"
    NOTE  = "note"
    LINK  = "link"
    TEXT  = "text"


class Category(str, Enum):
    TECHNOLOGY = "technology"
    SCIENCE    = "science"
    BUSINESS   = "business"
    EDUCATION  = "education"
    HEALTH     = "health"
    RELIGION   = "religion"
    PERSONAL   = "personal"
    ENTERTAINMENT = "entertainment"
    SPORTS        = "sports"
    PROGRAMMING   = "programming"
    FINANCE       = "finance"
    NEWS          = "news"
    SOCIAL        = "social"
    RESEARCH      = "research"
    PRODUCT       = "product"

    OTHER         = "other"

class Language(str, Enum):
    ARABIC  = "ar"
    ENGLISH = "en"
    MIXED   = "mixed"


class Memory(BaseModel):

    # ── Identity ──
    id: str = Field(
        default_factory=lambda: f"mem_{uuid.uuid4().hex[:12]}"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )

    # ── File Info ──
    file_name:  str      = Field(description="اسم الملف")
    file_type:  FileType = Field(description="نوع الملف")
    file_path:  str      = Field(description="مسار الملف")
    file_size:  int      = Field(default=0)
    file_hash:  str      = Field(default="")

    # ── Content ──
    raw_text:     str       = Field(default="")
    summary:      str       = Field(default="")
    key_concepts: list[str] = Field(default_factory=list)
    language:     Language  = Field(default=Language.MIXED)

    # ── AI Classification ──
    tags:             list[str] = Field(default_factory=list)
    category:         Category  = Field(default=Category.OTHER)
    importance_score: float     = Field(default=0.5, ge=0.0, le=1.0)

    # ── AI Fields ──
    keywords:        list[str] = Field(default_factory=list)
    entities:        list[str] = Field(default_factory=list)
    topics:          list[str] = Field(default_factory=list)
    main_topic:      str       = Field(default="")
    content_type:    str       = Field(default="")
    semantic_labels: list[str] = Field(default_factory=list)

    # ── Vision Fields ── ← جديد
    visual_summary:  str       = Field(
        default="",
        description="وصف بصري للصورة من الـ vision model"
    )
    detected_media:  list[str] = Field(
        default_factory=list,
        description="أفلام/مسلسلات/ألعاب مكتشفة"
    )
    brands:          list[str] = Field(
        default_factory=list,
        description="brands مكتشفة في الصورة"
    )
    products:        list[str] = Field(
        default_factory=list,
        description="منتجات مكتشفة"
    )
    people:          list[str] = Field(
        default_factory=list,
        description="أشخاص مكتشفين"
    )
    franchise:       str       = Field(
        default="",
        description="الـ franchise زي Marvel أو DC"
    )
    confidence_score: float    = Field(
        default=0.0,
        description="مدى ثقة الـ vision model في التحليل"
    )
    ocr_quality:     str       = Field(
        default="none",
        description="good|poor|none"
    )

    # ── Chunking ──
    chunks:       list[str] = Field(default_factory=list)
    chunk_ids:    list[str] = Field(default_factory=list)
    total_chunks: int       = Field(default=0)

    # ── User Behavior ──
    access_count:  int           = Field(default=0)
    last_accessed: Optional[str] = Field(default=None)
    is_favorite:   bool          = Field(default=False)
    user_rating:   Optional[int] = Field(default=None, ge=1, le=5)

    # ── Smart Scores ──
    recency_score: float = Field(default=1.0, ge=0.0, le=1.0)

    # ── Future ──
    related_memory_ids: list[str]     = Field(default_factory=list)
    source_url:         Optional[str] = Field(default=None)
    collection:         Optional[str] = Field(default=None)


class MemoryResponse(BaseModel):
    memory_id:    str
    file_name:    str
    file_type:    FileType
    summary:      str
    tags:         list[str]
    category:     Category
    importance:   float
    total_chunks: int
    status:       str = "success"


class MemorySearchResult(BaseModel):
    memory_id:        str
    file_name:        str
    file_path:        str
    summary:          str
    matched_text:     str
    tags:             list[str]
    created_at:       str
    final_score:      float
    semantic_score:   float
    recency_score:    float
    importance_score: float
    # Vision fields في الـ response
    visual_summary:   str       = Field(default="")
    content_type:     str       = Field(default="")
    detected_media:   list[str] = Field(default_factory=list)
    brands:           list[str] = Field(default_factory=list)
    people:           list[str] = Field(default_factory=list)


class MemorySearchResponse(BaseModel):
    query:         str
    total_results: int
    results:       list[MemorySearchResult]
    llm_answer:    Optional[str] = None