import os
from pathlib import Path

TEST_RUNTIME_DIR = "/tmp/second-brain-phase1-tests"
os.environ.setdefault("GROQ_API_KEY", "")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("UPLOAD_DIR", f"{TEST_RUNTIME_DIR}/uploads")
os.environ.setdefault("CHROMA_DIR", f"{TEST_RUNTIME_DIR}/chroma")
os.environ.setdefault("SESSIONS_DIR", f"{TEST_RUNTIME_DIR}/sessions")
os.environ.setdefault("GRAPH_DIR", f"{TEST_RUNTIME_DIR}/graph")
os.environ.setdefault("TEMP_AUDIO_DIR", f"{TEST_RUNTIME_DIR}/temp_audio")

import pytest

from app.core.config import settings
from app.services.session_service import SessionService


@pytest.fixture
def isolated_sessions(tmp_path, monkeypatch):
    sessions_dir = Path(tmp_path) / "sessions"
    monkeypatch.setattr(settings, "sessions_dir", sessions_dir)
    return SessionService()
