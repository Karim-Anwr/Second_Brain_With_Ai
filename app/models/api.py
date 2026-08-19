from typing import Literal

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class SearchScores(BaseModel):
    final: float
    semantic: float
    recency: float
    importance: float


class SearchResultResponse(BaseModel):
    memory_id: str
    file_name: str
    file_path: str
    summary: str
    matched_text: str
    tags: list[str]
    created_at: str
    scores: SearchScores


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResultResponse]
    llm_answer: str | None = None


class FavoriteResponse(BaseModel):
    memory_id: str
    is_favorite: bool
    status: Literal["updated"]


class RelatedMemoryResponse(BaseModel):
    memory_id: str
    relation_type: str
    score: float


class RelatedMemoriesResponse(BaseModel):
    memory_id: str
    total: int
    related: list[RelatedMemoryResponse]


class LinkMemoriesResponse(BaseModel):
    status: Literal["linked"]


class SessionListItem(BaseModel):
    id: str
    title: str
    total_messages: int
    created_at: str
    updated_at: str


class SessionListResponse(BaseModel):
    total: int
    sessions: list[SessionListItem]


class SessionMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class SessionDetailResponse(BaseModel):
    session_id: str
    title: str
    total_messages: int
    summary: str
    created_at: str
    messages: list[SessionMessageResponse]


class DeleteSessionResponse(BaseModel):
    status: Literal["deleted"]
    session_id: str


class SessionMemoryResponse(BaseModel):
    id: str
    type: str
    content: str
    importance: float
    keywords: list[str]
    created_at: str


class SessionMemoriesResponse(BaseModel):
    session_id: str
    total: int
    memories: list[SessionMemoryResponse]
