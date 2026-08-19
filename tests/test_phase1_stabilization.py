import asyncio
import io
import socket

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import Headers, UploadFile

from app.api.routes import chat as chat_routes
from app.api.routes import search as search_routes
from app.api.routes import upload as upload_routes
from app.core.config import settings
from app.core.exceptions import InvalidRequestException, UnsafeURLError, UnsupportedFileTypeException, UploadTooLargeException
from app.main import app
from app.models.memory import Category, FileType, MemoryResponse
from app.pipelines.ingest_pipeline import IngestPipeline
from app.services.link_service import LinkService
from app.utils.file_handler import save_upload_file


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def response(file_type: FileType = FileType.TEXT) -> MemoryResponse:
    return MemoryResponse(
        memory_id="mem_test",
        file_name="test",
        file_type=file_type,
        summary="summary",
        tags=[],
        category=Category.OTHER,
        importance=0.5,
        total_chunks=1,
    )


def test_text_upload_uses_existing_pipeline(client, monkeypatch):
    called = {}

    def process_text(text, title):
        called.update({"text": text, "title": title})
        return response()

    monkeypatch.setattr(upload_routes.ingest_pipeline, "process_text", process_text)
    result = client.post("/api/v1/upload/text", json={"title": "note", "text": "hello"})

    assert result.status_code == 200
    assert result.json()["file_type"] == "text"
    assert called == {"text": "hello", "title": "note"}


def test_process_text_delegates_to_shared_pipeline(monkeypatch):
    pipeline = IngestPipeline()
    captured = {}

    def process_content(**kwargs):
        captured.update(kwargs)
        return response()

    monkeypatch.setattr(pipeline, "_process_content", process_content)
    pipeline.process_text("مرحبا", "note")

    assert captured["file_type"] == "text"
    assert captured["file_path"] == ""
    assert captured["is_image"] is False


def test_file_type_coercion_preserves_all_supported_types():
    pipeline = IngestPipeline()
    assert pipeline._to_file_type("image") is FileType.IMAGE
    assert pipeline._to_file_type("pdf") is FileType.PDF
    assert pipeline._to_file_type("text") is FileType.TEXT
    assert pipeline._to_file_type("link") is FileType.LINK
    with pytest.raises(InvalidRequestException):
        pipeline._to_file_type("archive")


def test_chat_save_failure_does_not_abort_chat(monkeypatch):
    from app.models.conversation import ChatRequest
    from app.pipelines.conversation_pipeline import ConversationPipeline

    class Session:
        id = "session_aabbccdd"
        total_messages = 1

    monkeypatch.setattr("app.pipelines.conversation_pipeline.session_service.create_session", lambda: Session())
    monkeypatch.setattr("app.pipelines.conversation_pipeline.session_service.add_message", lambda **kwargs: type("Message", (), {"id": "msg_1"})())
    monkeypatch.setattr("app.pipelines.conversation_pipeline.llm_service.detect_save_intent", lambda _: {"wants_to_save": True, "confidence": 0.9})
    monkeypatch.setattr("app.pipelines.conversation_pipeline.conversation_service.save_as_memory", lambda **_: (_ for _ in ()).throw(RuntimeError("save failed")))
    monkeypatch.setattr("app.pipelines.conversation_pipeline.context_builder.build", lambda **_: {"context": "ctx", "memory_ids_used": []})
    monkeypatch.setattr("app.pipelines.conversation_pipeline.context_builder.build_system_prompt", lambda: "system")
    monkeypatch.setattr("app.pipelines.conversation_pipeline.llm_service._call", lambda *_, **__: "answer")
    monkeypatch.setattr("app.pipelines.conversation_pipeline.conversation_service.process_and_extract", lambda **_: [])

    result = ConversationPipeline().chat(ChatRequest(message="save this"))
    assert result.answer == "answer"
    assert result.new_memories == 0


def test_favorite_route_uses_singleton_binding(client, monkeypatch):
    class Storage:
        def set_favorite(self, memory_id, is_favorite):
            return memory_id == "mem_1" and is_favorite

    monkeypatch.setattr(search_routes, "storage_service", Storage())
    result = client.post("/api/v1/memories/favorite", json={"memory_id": "mem_1", "is_favorite": True})
    assert result.status_code == 200
    assert result.json()["status"] == "updated"


def test_session_listing_skips_sidecars_and_malformed_files(isolated_sessions):
    session = isolated_sessions.create_session()
    (isolated_sessions.sessions_dir / f"{session.id}_memories.json").write_text("[]", encoding="utf-8")
    (isolated_sessions.sessions_dir / "session_badbad00.json").write_text("not-json", encoding="utf-8")
    assert [item["id"] for item in isolated_sessions.list_sessions()] == [session.id]


def test_unknown_session_api_returns_stable_404(client, isolated_sessions, monkeypatch):
    monkeypatch.setattr(chat_routes, "session_service", isolated_sessions)
    result = client.get("/api/v1/sessions/session_deadbeef")
    assert result.status_code == 404
    assert result.json()["error"]["code"] == "resource_not_found"


def test_delete_session_removes_sidecar(client, isolated_sessions, monkeypatch):
    session = isolated_sessions.create_session()
    sidecar = isolated_sessions.sessions_dir / f"{session.id}_memories.json"
    sidecar.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(chat_routes, "session_service", isolated_sessions)

    result = client.delete(f"/api/v1/sessions/{session.id}")
    assert result.status_code == 200
    assert not sidecar.exists()
    assert not (isolated_sessions.sessions_dir / f"{session.id}.json").exists()


def test_graph_routes_validate_depth_and_memory_ids(client, monkeypatch):
    class Storage:
        def memory_exists(self, memory_id):
            return memory_id == "mem_1"

    class Graph:
        def get_related(self, memory_id, depth):
            return []

        def add_edge(self, *args, **kwargs):
            return True

    monkeypatch.setattr(search_routes, "storage_service", Storage())
    monkeypatch.setattr(search_routes, "graph_service", Graph())
    invalid_depth = client.get("/api/v1/memories/mem_1/related?depth=99")
    missing_memory = client.post("/api/v1/memories/link", json={"from_id": "mem_1", "to_id": "mem_missing"})
    assert invalid_depth.status_code == 422
    assert missing_memory.status_code == 404


def upload_file(content: bytes, content_type: str, name: str = "upload.png") -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=name, headers=Headers({"content-type": content_type}))


def test_upload_size_and_signature_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    monkeypatch.setattr(settings, "max_upload_size_bytes", 8)
    with pytest.raises(UploadTooLargeException):
        asyncio.run(save_upload_file(upload_file(b"\x89PNG\r\n\x1a\nmore", "image/png")))
    assert not list(tmp_path.iterdir())

    monkeypatch.setattr(settings, "max_upload_size_bytes", 1024)
    with pytest.raises(UnsupportedFileTypeException):
        asyncio.run(save_upload_file(upload_file(b"plain text", "image/png")))
    assert not list(tmp_path.iterdir())


def test_link_validation_rejects_unsafe_destinations(monkeypatch):
    service = LinkService()

    def resolver(host, *args, **kwargs):
        address = "127.0.0.1" if host == "localhost" else "10.0.0.7" if host == "private.test" else "8.8.8.8"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]

    monkeypatch.setattr("app.services.link_service.socket.getaddrinfo", resolver)
    assert service.validate_url("https://public.example/path") == "https://public.example/path"
    with pytest.raises(UnsafeURLError):
        service.validate_url("http://localhost/admin")
    with pytest.raises(UnsafeURLError):
        service.validate_url("https://private.test/")
    with pytest.raises(UnsafeURLError):
        service.validate_url("file:///etc/passwd")


def test_redirect_to_private_destination_is_rejected(monkeypatch):
    service = LinkService()

    def resolver(host, *args, **kwargs):
        address = "127.0.0.1" if host == "private.test" else "8.8.8.8"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]

    class Redirect:
        status_code = 302
        headers = {"Location": "http://private.test/internal"}

        def close(self):
            return None

    monkeypatch.setattr("app.services.link_service.socket.getaddrinfo", resolver)
    monkeypatch.setattr("app.services.link_service.requests.get", lambda *_, **__: Redirect())
    with pytest.raises(UnsafeURLError):
        service._safe_get("https://public.example/")


def test_unexpected_error_uses_safe_response(client, monkeypatch):
    monkeypatch.setattr(search_routes.search_pipeline, "search", lambda **_: (_ for _ in ()).throw(RuntimeError("secret filesystem path")))
    result = client.post("/api/v1/search", json={"query": "anything"})
    assert result.status_code == 500
    assert result.json()["error"]["code"] == "internal_error"
    assert "secret filesystem path" not in result.text
