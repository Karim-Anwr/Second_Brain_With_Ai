import json
from pathlib import Path
from datetime import datetime
from app.models.conversation import (
    ChatSession, ChatMessage, MessageRole, ExtractedMemory
)
from app.core.config import settings


class SessionService:
    """
    مسؤول عن حفظ وجلب الـ sessions.
    
    دلوقتي: بيحفظ على الـ disk كـ JSON
    Phase 2: هنغيره لـ PostgreSQL أو Redis
    
    ليه JSON دلوقتي؟
    عشان نبدأ سريع من غير ما نحتاج database تانية.
    """

    def __init__(self):
        self.sessions_dir = Path("storage/sessions")
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        print("✅ Session Service جاهز!")

    # ============================================================
    # Session Management
    # ============================================================

    def create_session(self) -> ChatSession:
        """اعمل session جديدة"""
        session = ChatSession()
        self._save_session(session)
        print(f"✅ Session جديدة: {session.id}")
        return session

    def get_session(self, session_id: str) -> ChatSession:
        """جيب session موجودة"""
        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            # لو مش موجودة اعمل جديدة
            return self.create_session()

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ChatSession(**data)

    def _save_session(self, session: ChatSession):
        """احفظ الـ session على الـ disk"""
        path = self.sessions_dir / f"{session.id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session.model_dump(), f, ensure_ascii=False, indent=2)

    def list_sessions(self) -> list[dict]:
        """جيب كل الـ sessions"""
        sessions = []
        for path in sorted(
            self.sessions_dir.glob("*.json"),
            reverse=True
        )[:20]:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sessions.append({
                "id":           data["id"],
                "title":        data.get("title", "محادثة"),
                "total_messages": data.get("total_messages", 0),
                "created_at":   data.get("created_at", ""),
                "updated_at":   data.get("updated_at", ""),
            })
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """امسح session"""
        path = self.sessions_dir / f"{session_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    # ============================================================
    # Message Management
    # ============================================================

    def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        memory_ids: list[str] = None,
    ) -> ChatMessage:
        """ضيف رسالة للـ session"""
        session = self.get_session(session_id)

        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            memory_ids=memory_ids or [],
        )

        session.messages.append(message)
        session.total_messages += 1
        session.updated_at = datetime.now().isoformat()

        # لو أول رسالة — اعمل عنوان من أول 50 حرف
        if session.total_messages == 1 and role == MessageRole.USER:
            session.title = content[:50] + ("..." if len(content) > 50 else "")

        self._save_session(session)
        return message

    def get_recent_messages(
        self,
        session_id: str,
        last_n: int = 10,
    ) -> list[ChatMessage]:
        """
        جيب آخر N رسائل من الـ session.
        دي الـ Short-Term Memory.
        """
        session = self.get_session(session_id)
        return session.messages[-last_n:]

    def update_session_summary(
        self,
        session_id: str,
        summary: str,
    ):
        """حدّث ملخص الـ session"""
        session = self.get_session(session_id)
        session.summary = summary
        self._save_session(session)

    # ============================================================
    # Extracted Memories Storage
    # ============================================================

    def save_extracted_memory(
        self,
        session_id: str,
        memory: ExtractedMemory,
    ):
        """احفظ ذكرى مستخرجة من المحادثة"""
        path = self.sessions_dir / f"{session_id}_memories.json"

        memories = []
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                memories = json.load(f)

        memories.append(memory.model_dump())

        with open(path, "w", encoding="utf-8") as f:
            json.dump(memories, f, ensure_ascii=False, indent=2)

    def get_extracted_memories(
        self,
        session_id: str,
    ) -> list[ExtractedMemory]:
        """جيب كل الذكريات المستخرجة من session"""
        path = self.sessions_dir / f"{session_id}_memories.json"
        if not path.exists():
            return []

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [ExtractedMemory(**m) for m in data]


# Singleton
_session_service = None

def get_session_service():
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service

session_service = get_session_service()