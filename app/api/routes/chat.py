from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUser
from app.auth.dependencies import get_current_user
from app.core.exceptions import InvalidRequestException, ResourceNotFoundException
from app.db.session import get_db
from app.models.api import (
    DeleteSessionResponse,
    SessionDetailResponse,
    SessionListResponse,
    SessionMemoriesResponse,
    error_responses,
)
from app.models.conversation import ChatRequest, ChatResponse
from app.pipelines.conversation_pipeline import conversation_pipeline
from app.services.session_service import session_service
from app.utils.pagination import decode_cursor, encode_cursor


router = APIRouter()


@router.post("/chat", response_model=ChatResponse, responses=error_responses(401, 404, 422, 500, 503))
async def chat(
    request: ChatRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    result = conversation_pipeline.chat_owned(db, current_user.id, request)
    db.commit()
    return result


@router.get("/sessions", response_model=SessionListResponse, responses=error_responses(401, 422, 500, 503))
async def list_sessions(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=512),
):
    sessions = session_service.list_sessions_owned(db, current_user.id)
    ordered = sorted(sessions, key=lambda item: item["id"])
    ordered.sort(key=lambda item: item["updated_at"], reverse=True)
    position = decode_cursor(cursor, "sessions")
    start = _cursor_start(ordered, position, lambda item: [item["updated_at"], item["id"]])
    page = ordered[start : start + limit]
    next_cursor = _next_cursor("sessions", page, start, limit, len(ordered), lambda item: [item["updated_at"], item["id"]])
    return {"total": len(ordered), "limit": limit, "next_cursor": next_cursor, "sessions": page}


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse, responses=error_responses(401, 404, 422, 500, 503))
async def get_session(
    session_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=512),
):
    session = session_service.get_session_owned(db, current_user.id, session_id)
    ordered = sorted(session.messages, key=lambda item: (item.created_at, item.id))
    position = decode_cursor(cursor, "session_messages")
    start = _cursor_start(ordered, position, lambda item: [item.created_at, item.id])
    page = ordered[start : start + limit]
    next_cursor = _next_cursor("session_messages", page, start, limit, len(ordered), lambda item: [item.created_at, item.id])
    return {
        "session_id": session.id,
        "title": session.title,
        "total_messages": session.total_messages,
        "summary": session.summary,
        "created_at": session.created_at,
        "limit": limit,
        "next_cursor": next_cursor,
        "messages": [
            {"id": message.id, "role": message.role.value, "content": message.content, "created_at": message.created_at}
            for message in page
        ],
    }


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse, responses=error_responses(401, 404, 500, 503))
async def delete_session(
    session_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if not session_service.delete_session_owned(db, current_user.id, session_id):
        raise ResourceNotFoundException("Session")
    return {"status": "deleted", "session_id": session_id}


@router.get("/sessions/{session_id}/memories", response_model=SessionMemoriesResponse, responses=error_responses(401, 404, 422, 500, 503))
async def get_session_memories(
    session_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=512),
):
    memories = session_service.get_extracted_memories_owned(db, current_user.id, session_id)
    ordered = sorted(memories, key=lambda item: (item.created_at, item.id))
    position = decode_cursor(cursor, "session_memories")
    start = _cursor_start(ordered, position, lambda item: [item.created_at, item.id])
    page = ordered[start : start + limit]
    next_cursor = _next_cursor("session_memories", page, start, limit, len(ordered), lambda item: [item.created_at, item.id])
    return {
        "session_id": session_id,
        "total": len(ordered),
        "limit": limit,
        "next_cursor": next_cursor,
        "memories": [
            {
                "id": memory.id,
                "type": memory.memory_type.value,
                "content": memory.content,
                "importance": memory.importance,
                "keywords": memory.keywords,
                "created_at": memory.created_at,
            }
            for memory in page
        ],
    }


def _cursor_start(items, position: list[str] | None, key):
    if position is None:
        return 0
    for index, item in enumerate(items):
        if key(item) == position:
            return index + 1
    raise InvalidRequestException("The pagination cursor is invalid.")


def _next_cursor(kind: str, page, start: int, limit: int, total: int, key) -> str | None:
    if not page or start + limit >= total:
        return None
    return encode_cursor(kind, key(page[-1]))
