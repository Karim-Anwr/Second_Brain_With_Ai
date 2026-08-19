from fastapi import APIRouter

from app.core.exceptions import ResourceNotFoundException
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
async def chat(request: ChatRequest):
    return conversation_pipeline.chat(request)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    sessions = session_service.list_sessions()
    return {"total": len(sessions), "sessions": sessions}


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str):
    session = session_service.get_session(session_id)
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
async def delete_session(session_id: str):
    if not session_service.delete_session(session_id):
        raise ResourceNotFoundException("Session")
    return {"status": "deleted", "session_id": session_id}


@router.get("/sessions/{session_id}/memories", response_model=SessionMemoriesResponse)
async def get_session_memories(session_id: str):
    session_service.get_session(session_id)
    memories = session_service.get_extracted_memories(session_id)
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
