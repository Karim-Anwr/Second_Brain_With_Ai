import json
import logging
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.exceptions import InvalidRequestException, ResourceNotFoundException
from app.models.conversation import ChatMessage, ChatSession, ExtractedMemory, MessageRole


logger = logging.getLogger(__name__)
SESSION_ID_PATTERN = re.compile(r"^session_[a-f0-9]{8}$")


class SessionService:
    """Local JSON session persistence with per-process locking and atomic replacement."""

    def __init__(self):
        self.sessions_dir = Path(settings.sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        print("✅ Session Service جاهز!")

    @staticmethod
    def _validate_session_id(session_id: str) -> str:
        if not SESSION_ID_PATTERN.fullmatch(session_id):
            raise InvalidRequestException("The session identifier is invalid.")
        return session_id

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{self._validate_session_id(session_id)}.json"

    def _memories_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{self._validate_session_id(session_id)}_memories.json"

    def _atomic_write_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
            ) as temp_file:
                temporary_name = temp_file.name
                json.dump(value, temp_file, ensure_ascii=False, indent=2)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temporary_name, path)
        finally:
            if temporary_name and Path(temporary_name).exists():
                Path(temporary_name).unlink(missing_ok=True)

    def _load_json(self, path: Path) -> Any:
        with open(path, "r", encoding="utf-8") as source:
            return json.load(source)

    def create_session(self) -> ChatSession:
        session = ChatSession()
        self._save_session(session)
        return session

    def get_session(self, session_id: str) -> ChatSession:
        path = self._session_path(session_id)
        if not path.exists():
            raise ResourceNotFoundException("Session")
        try:
            data = self._load_json(path)
            if not isinstance(data, dict) or data.get("id") != session_id:
                raise ValueError("invalid session shape")
            return ChatSession(**data)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("Unable to read session %s", session_id, exc_info=exc)
            raise ResourceNotFoundException("Session") from exc

    def _save_session(self, session: ChatSession) -> None:
        with self._lock:
            self._atomic_write_json(self._session_path(session.id), session.model_dump(mode="json"))

    def list_sessions(self) -> list[dict]:
        sessions: list[dict] = []
        for path in sorted(self.sessions_dir.glob("session_*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            if path.name.endswith("_memories.json"):
                continue
            try:
                data = self._load_json(path)
                if not isinstance(data, dict) or not SESSION_ID_PATTERN.fullmatch(str(data.get("id", ""))):
                    raise ValueError("invalid session shape")
                sessions.append(
                    {
                        "id": data["id"],
                        "title": data.get("title", "محادثة"),
                        "total_messages": data.get("total_messages", 0),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", ""),
                    }
                )
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                logger.warning("Skipping unreadable session file %s", path.name, exc_info=exc)
            if len(sessions) >= 20:
                break
        return sessions

    def delete_session(self, session_id: str) -> bool:
        session_path = self._session_path(session_id)
        memories_path = self._memories_path(session_id)
        with self._lock:
            if not session_path.exists():
                return False
            session_path.unlink()
            memories_path.unlink(missing_ok=True)
        return True

    def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        memory_ids: list[str] | None = None,
    ) -> ChatMessage:
        with self._lock:
            session = self.get_session(session_id)
            message = ChatMessage(session_id=session_id, role=role, content=content, memory_ids=memory_ids or [])
            session.messages.append(message)
            session.total_messages += 1
            session.updated_at = datetime.now().isoformat()
            if session.total_messages == 1 and role == MessageRole.USER:
                session.title = content[:50] + ("..." if len(content) > 50 else "")
            self._save_session(session)
            return message

    def get_recent_messages(self, session_id: str, last_n: int = 10) -> list[ChatMessage]:
        return self.get_session(session_id).messages[-last_n:]

    def update_session_summary(self, session_id: str, summary: str) -> None:
        with self._lock:
            session = self.get_session(session_id)
            session.summary = summary
            self._save_session(session)

    def save_extracted_memory(self, session_id: str, memory: ExtractedMemory) -> None:
        path = self._memories_path(session_id)
        with self._lock:
            memories: list[dict] = []
            if path.exists():
                try:
                    data = self._load_json(path)
                    if isinstance(data, list):
                        memories = data
                    else:
                        raise ValueError("invalid extracted memory shape")
                except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
                    logger.warning("Replacing unreadable extracted-memory sidecar for %s", session_id, exc_info=exc)
            memories.append(memory.model_dump(mode="json"))
            self._atomic_write_json(path, memories)

    def get_extracted_memories(self, session_id: str) -> list[ExtractedMemory]:
        path = self._memories_path(session_id)
        if not path.exists():
            return []
        try:
            data = self._load_json(path)
            if not isinstance(data, list):
                raise ValueError("invalid extracted memory shape")
            return [ExtractedMemory(**memory) for memory in data]
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("Unable to read extracted memories for %s", session_id, exc_info=exc)
            return []


_session_service: SessionService | None = None


def get_session_service() -> SessionService:
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service


session_service = get_session_service()
