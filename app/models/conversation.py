from pydantic import BaseModel, Field ,field_validator
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid



class MemoryType(str, Enum):
    FACT         = "fact"
    PREFERENCE   = "preference"
    GOAL         = "goal"
    TASK         = "task"
    RELATIONSHIP = "relationship"
    CONVERSATION = "conversation"
    PERSONAL_INFO = "personal_info"
    PROJECT      = "project"
    SKILL        = "skill"


class MessageRole(str, Enum):
    USER      = "user"
    ASSISTANT = "assistant"
    SYSTEM    = "system"


class ChatMessage(BaseModel):
    """رسالة واحدة في المحادثة"""
    id: str = Field(
        default_factory=lambda: f"msg_{uuid.uuid4().hex[:8]}"
    )
    session_id:  str
    role:        MessageRole
    content:     str
    created_at:  str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    # معلومات إضافية
    tokens_used: int        = Field(default=0)
    memory_ids:  list[str]  = Field(default_factory=list)
    # الـ memories اللي استخدمها في الرد


class ChatSession(BaseModel):
    """جلسة محادثة كاملة"""
    id: str = Field(
        default_factory=lambda: f"session_{uuid.uuid4().hex[:8]}"
    )
    created_at:   str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    updated_at:   str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    title:        str        = Field(default="محادثة جديدة")
    messages:     list[ChatMessage] = Field(default_factory=list)
    total_messages: int      = Field(default=0)
    summary:      str        = Field(default="")
    # ملخص المحادثة كلها — بيتعمل تلقائي


class ExtractedMemory(BaseModel):
    """ذكرى مستخرجة من المحادثة"""
    id: str = Field(
        default_factory=lambda: f"exmem_{uuid.uuid4().hex[:8]}"
    )
    session_id:   str
    memory_type:  MemoryType
    content:      str
    summary:      str        = Field(default="")
    keywords:     list[str]  = Field(default_factory=list)
    entities:     list[str]  = Field(default_factory=list)
    topics:       list[str]  = Field(default_factory=list)
    importance:   float      = Field(default=0.5, ge=0.0, le=1.0)
    created_at:   str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    source_message_id: str   = Field(default="")


class ConversationMemory(BaseModel):
    """
    الذاكرة الكاملة للمحادثة.
    بتجمع الـ short-term والـ long-term.
    """
    session_id:       str
    recent_messages:  list[ChatMessage]   = Field(default_factory=list)
    relevant_memories: list[dict]         = Field(default_factory=list)
    extracted_facts:  list[ExtractedMemory] = Field(default_factory=list)
    context_summary:  str                 = Field(default="")


# ── API Models ──


class ChatRequest(BaseModel):
    session_id: Optional[str] = Field(default=None)
    message:    str           = Field(..., min_length=1, max_length=2000)

    @field_validator("session_id")
    @classmethod
    def normalize_session_id(cls, v):
        if v is None or v.strip().lower() in ("none", "null", ""):
            return None
        return v

class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer:     str
    memories_used: list[str] = Field(default_factory=list)
    new_memories:  int       = Field(default=0)