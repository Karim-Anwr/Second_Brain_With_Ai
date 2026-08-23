from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUser
from app.auth.dependencies import get_current_user
from app.core.exceptions import ResourceNotFoundException
from app.db.session import get_db
from app.models.api import (
    DeleteSessionResponse,
    SessionDetailResponse,
    SessionListResponse,
    SessionMemoriesResponse,
)
from app.models.conversation import ChatRequest, ChatResponse
from app.pipelines.conversation_pipeline import conversation_pipeline
from app.services.session_service import session_service


router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    result = conversation_pipeline.chat_owned(db, current_user.id, request)
    db.commit()
    return result


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    sessions = session_service.list_sessions_owned(db, current_user.id)
    return {"total": len(sessions), "sessions": sessions}


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    session = session_service.get_session_owned(db, current_user.id, session_id)
    return {
        "session_id": session.id,
        "title": session.title,
        "total_messages": session.total_messages,
        "summary": session.summary,
        "created_at": session.created_at,
        "messages": [
            {"id": message.id, "role": message.role.value, "content": message.content, "created_at": message.created_at}
            for message in session.messages
        ],
    }


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(
    session_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if not session_service.delete_session_owned(db, current_user.id, session_id):
        raise ResourceNotFoundException("Session")
    return {"status": "deleted", "session_id": session_id}


@router.get("/sessions/{session_id}/memories", response_model=SessionMemoriesResponse)
async def get_session_memories(
    session_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    memories = session_service.get_extracted_memories_owned(db, current_user.id, session_id)
    return {
        "session_id": session_id,
        "total": len(memories),
        "memories": [
            {
                "id": memory.id,
                "type": memory.memory_type.value,
                "content": memory.content,
                "importance": memory.importance,
                "keywords": memory.keywords,
                "created_at": memory.created_at,
            }
            for memory in memories
        ],
    }
