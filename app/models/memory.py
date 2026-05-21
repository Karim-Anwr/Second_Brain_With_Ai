from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


# ============================================================
# ENUMS
# ============================================================

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


# ============================================================
# MEMORY (Internal Storage Model)
# ============================================================

class Memory(BaseModel):

    # ─────────────────────────────
    # Identity
    # ─────────────────────────────
    id: str = Field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:12]}")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # ─────────────────────────────
    # File Info
    # ─────────────────────────────
    file_name: str
    file_type: FileType
    file_path: str
    file_size: int = 0
    file_hash: str = ""

    # ─────────────────────────────
    # Content
    # ─────────────────────────────
    raw_text: str = ""
    summary: str = ""
    key_concepts: list[str] = []
    language: Language = Language.MIXED

    # ─────────────────────────────
    # AI Classification
    # ─────────────────────────────
    tags: list[str] = []
    category: Category = Category.OTHER
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)

    # ─────────────────────────────
    # AI Enrichment
    # ─────────────────────────────
    keywords: list[str] = []
    entities: list[str] = []
    topics: list[str] = []
    main_topic: str = ""
    content_type: str = ""
    semantic_labels: list[str] = []

    # ─────────────────────────────
    # Chunking
    # ─────────────────────────────
    chunks: list[str] = []
    chunk_ids: list[str] = []
    total_chunks: int = 0

    # ─────────────────────────────
    # Behavior
    # ─────────────────────────────
    access_count: int = 0
    last_accessed: Optional[str] = None
    is_favorite: bool = False
    user_rating: Optional[int] = Field(default=None, ge=1, le=5)

    # ─────────────────────────────
    # Scoring
    # ─────────────────────────────
    recency_score: float = 1.0

    # ─────────────────────────────
    # Future
    # ─────────────────────────────
    related_memory_ids: list[str] = []
    source_url: Optional[str] = None
    collection: Optional[str] = None


# ============================================================
# MEMORY RESPONSE (FULL API OUTPUT)
# ============================================================

class MemoryResponse(BaseModel):

    memory_id: str
    file_name: str
    file_type: FileType
    summary: str

    # AI Output
    tags: list[str] = []
    keywords: list[str] = []
    entities: list[str] = []
    topics: list[str] = []

    category: Category
    language: Language
    importance: float

    # Extra AI metadata
    main_topic: str = ""
    content_type: str = ""
    semantic_labels: list[str] = []

    # Structure
    total_chunks: int

    # Status
    status: str


# ============================================================
# SEARCH RESULT (FULL EXPLAINABLE VERSION)
# ============================================================

class MemorySearchResult(BaseModel):

    memory_id: str
    file_name: str
    file_path: str
    summary: str

    matched_text: str

    # AI metadata
    tags: list[str] = []
    keywords: list[str] = []
    entities: list[str] = []
    topics: list[str] = []

    category: str = ""
    language: str = ""
    content_type: str = ""

    # Time
    created_at: str = ""

    # Scores
    final_score: float
    semantic_score: float
    recency_score: float
    importance_score: float

    # Explainability
    keyword_boost: float = 0.0
    entity_boost: float = 0.0
    rerank_score: float = 0.0


# ============================================================
# SEARCH RESPONSE
# ============================================================

class MemorySearchResponse(BaseModel):

    query: str
    total: int
    results: list[MemorySearchResult]
    llm_answer: Optional[str] = None