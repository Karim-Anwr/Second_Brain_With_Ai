from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


# ============================================================
# Enums — القيم الثابتة
# ============================================================

class FileType(str, Enum):
    IMAGE = "image"
    PDF   = "pdf"
    NOTE  = "note"      
    LINK  = "link" 
    TEXT  = "text"   

class Category(str, Enum):
    TECHNOLOGY  = "technology"
    SCIENCE     = "science"
    BUSINESS    = "business"
    EDUCATION   = "education"
    HEALTH      = "health"
    RELIGION    = "religion"
    PERSONAL    = "personal"
    OTHER       = "other"

class Language(str, Enum):
    ARABIC  = "ar"
    ENGLISH = "en"
    MIXED   = "mixed"


# ============================================================
# Memory Object — الذاكرة الكاملة
# ============================================================

class Memory(BaseModel):
    """
    ده مش بس document — ده ذكرى كاملة.
    
    كل حاجة المستخدم يحفظها بتبقا Memory Object
    فيها كل المعلومات اللي محتاجينها عشان نجيبها
    بطريقة ذكية بعدين.
    """

    # 1. IDENTITY — هوية الذاكرة

    id: str = Field(
        default_factory=lambda: f"mem_{uuid.uuid4().hex[:12]}",
        description="ID فريد لكل ذكرى"
    )
    # ليه مش uuid عادي؟
    # عشان "mem_abc123" أوضح في الـ logs من "abc123"

    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="امتى اتحفظت"
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="امتى اتعدلت"
    )

    # 2. FILE INFO — معلومات الملف

    file_name: str = Field(description="اسم الملف الأصلي")
    file_type: FileType = Field(description="نوع الملف")
    file_path: str = Field(description="مسار الملف على الـ disk")
    file_size: int = Field(default=0, description="حجم الملف بالـ bytes")
    file_hash: str = Field(
        default="",
        description="MD5 hash — يكتشف لو نفس الملف اترفع تاني"
    )

    # 3. CONTENT — المحتوى

    # OCR + AI يعملوها

    raw_text: str = Field(
        default="",
        description="النص الخام اللي طلع من OCR"
    )
    summary: str = Field(
        default="",
        description="""
        ملخص من 2-3 جمل — AI يعمله.
        ليه مهم؟
        لأن لما الـ LLM بيجاوب على سؤال،
        بيبعتله الـ summary مش الـ raw_text كله.
        بيوفر tokens ويبقا أسرع.
        """
    )
    key_concepts: list[str] = Field(
        default=[],
        description="""
        المفاهيم الأساسية — AI يستخرجها.
        مثال: ["neural networks", "backpropagation", "gradient descent"]
        أدق من الـ tags وبتساعد في الـ search.
        """
    )
    language: Language = Field(
        default=Language.MIXED,
        description="لغة المحتوى — AI يحددها"
    )

    # 4. AI CLASSIFICATION — تصنيف AI

    tags: list[str] = Field(
        default=[],
        description="""
        كلمات مفتاحية — AI يولدها.
        مثال: ["machine learning", "python", "tutorial"]
        بتستخدم في الـ filter قبل الـ vector search.
        """
    )
    category: Category = Field(
        default=Category.OTHER,
        description="""
        تصنيف رئيسي — AI يحدده.
        بيساعد في الـ filter السريع.
        مثال: technology, science, personal
        """
    )
    importance_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="""
        مدى أهمية الذاكرة من 0 لـ 1 — AI يحددها.
        بيأثر في الـ ranking:
        0.9 = مهم جداً (يطلع فوق)
        0.3 = أقل أهمية (يطلع تحت)
        """
    )

    # 5. CHUNKING — تقسيم النص

    chunks: list[str] = Field(
        default=[],
        description="""
        النص مقسم لأجزاء صغيرة.
        كل chunk بيتحول لـ vector لوحده.
        ليه؟ عشان الـ search يبقا أدق —
        بدل ما يجيب الملف كله، بيجيب الجزء اللي فيه الإجابة.
        """
    )
    chunk_ids: list[str] = Field(
        default=[],
        description="IDs الـ chunks في ChromaDB"
    )
    total_chunks: int = Field(
        default=0,
        description="عدد الـ chunks"
    )

    # 6. USER BEHAVIOR — سلوك المستخدم
    # بتتحدث تلقائي مع الوقت

    access_count: int = Field(
        default=0,
        description="""
        كام مرة المستخدم فتح أو رجع للذاكرة دي.
        كلما زاد = أهم في الـ ranking.
        ده بيخلي النظام يتعلم من سلوكك.
        """
    )
    last_accessed: Optional[str] = Field(
        default=None,
        description="آخر مرة المستخدم رجع عليها"
    )
    is_favorite: bool = Field(
        default=False,
        description="المستخدم ضغط نجمة — بيرفعها في الـ ranking دايماً"
    )
    user_rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="تقييم المستخدم من 1 لـ 5 — اختياري"
    )

    # 7. SMART SCORES — نتيجة الذكاء
    # بتتحسب تلقائي

    recency_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="""
        بيقل مع الوقت تلقائي.
        اليوم الأول  = 1.0
        بعد أسبوع   = 0.7
        بعد شهر     = 0.4
        بعد سنة     = 0.1
        """
    )

    # 8. FUTURE — Phase 3

    related_memory_ids: list[str] = Field(
        default=[],
        description="IDs لـ memories تانية ليها علاقة — Memory Graph"
    )
    source_url: Optional[str] = Field(
        default=None,
        description="لو جاي من link — Phase 2"
    )
    collection: Optional[str] = Field(
        default=None,
        description="اسم المجموعة — زي folders — Phase 2"
    )


# ============================================================
# Response Models — شكل الـ API responses
# ============================================================

class MemoryResponse(BaseModel):
    """اللي بيرجع للمستخدم بعد الـ upload"""
    memory_id:     str
    file_name:     str
    file_type:     FileType
    summary:       str
    tags:          list[str]
    category:      Category
    importance:    float
    total_chunks:  int
    status:        str = "success"


class MemorySearchResult(BaseModel):
    """نتيجة واحدة في الـ search"""
    memory_id:    str
    file_name:    str
    file_path:    str
    summary:      str
    matched_text: str       # الـ chunk اللي فيه الإجابة بالظبط
    tags:         list[str]
    created_at:   str
    final_score:  float     # الـ score النهائي بعد الـ ranking
    semantic_score:   float # مدى قرب المعنى
    recency_score:    float # مدى حداثة الذاكرة
    importance_score: float # مدى أهميتها


class MemorySearchResponse(BaseModel):
    """الـ response الكامل للـ search"""
    query:           str
    total_results:   int
    results:         list[MemorySearchResult]
    llm_answer:      Optional[str] = None  # إجابة الـ LLM — Phase 2