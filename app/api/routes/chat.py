from fastapi import APIRouter, HTTPException
from app.models.conversation import (
    ChatRequest,
    ChatResponse,
)
from app.pipelines.conversation_pipeline import conversation_pipeline
from app.services.session_service import session_service

router = APIRouter()


# ============================================================
# Chat — المحادثة الرئيسية
# ============================================================

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    الـ endpoint الرئيسي للمحادثة.
    
    لو session_id = None → هيعمل session جديدة
    لو session_id موجود → هيكمل المحادثة
    
    مثال:
    {
        "message": "إيه أحسن كتاب عن ML؟",
        "session_id": null
    }
    """
    try:
        response = conversation_pipeline.chat(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Sessions
# ============================================================

@router.get("/sessions")
async def list_sessions():
    """جيب كل الـ sessions"""
    try:
        sessions = session_service.list_sessions()
        return {
            "total":    len(sessions),
            "sessions": sessions,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """جيب session معينة مع كل رسايلها"""
    try:
        session = session_service.get_session(session_id)
        return {
            "session_id":     session.id,
            "title":          session.title,
            "total_messages": session.total_messages,
            "summary":        session.summary,
            "created_at":     session.created_at,
            "messages": [
                {
                    "id":         m.id,
                    "role":       m.role.value,
                    "content":    m.content,
                    "created_at": m.created_at,
                }
                for m in session.messages
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """امسح session"""
    try:
        success = session_service.delete_session(session_id)
        return {
            "status":  "deleted" if success else "not_found",
            "session_id": session_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Memories
# ============================================================

@router.get("/sessions/{session_id}/memories")
async def get_session_memories(session_id: str):
    """جيب الذكريات المستخرجة من session"""
    try:
        memories = session_service.get_extracted_memories(session_id)
        return {
            "session_id": session_id,
            "total":      len(memories),
            "memories": [
                {
                    "id":          m.id,
                    "type":        m.memory_type.value,
                    "content":     m.content,
                    "importance":  m.importance,
                    "keywords":    m.keywords,
                    "created_at":  m.created_at,
                }
                for m in memories
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))