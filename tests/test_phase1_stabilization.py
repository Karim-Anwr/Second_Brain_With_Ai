import asyncio
import io
import socket
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import Headers, UploadFile

from app.api.routes import chat as chat_routes
from app.api.routes import search as search_routes
from app.api.routes import upload as upload_routes
from app.auth.current_user import CurrentUser
from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.core.exceptions import (
    InvalidRequestException,
    ResourceNotFoundException,
    StorageCorruptionException,
    StorageException,
    UnsafeURLError,
    UnsupportedFileTypeException,
    UploadTooLargeException,
)
from app.main import app
from app.models.conversation import ExtractedMemory, MemoryType
from app.models.memory import Category, FileType, MemoryResponse
from app.pipelines.ingest_pipeline import IngestPipeline
from app.db.session import get_db
from app.services.graph_service import GraphService
from app.services.link_service import LinkService
from app.utils.file_handler import save_upload_file


@pytest.fixture
def client():
    db = type("RouteDb", (), {"commit": lambda self: None, "rollback": lambda self: None})()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(UUID("10000000-0000-0000-0000-000000000001"))
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


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

    def process_text_owned(db, owner_user_id, text, title):
        called.update({"db": db, "owner_user_id": owner_user_id, "text": text, "title": title})
        return response()

    monkeypatch.setattr(upload_routes.ingest_pipeline, "process_text_owned", process_text_owned)
    result = client.post("/api/v1/upload/text", json={"title": "note", "text": "hello"})

    assert result.status_code == 200
    assert result.json()["file_type"] == "text"
    assert called["text"] == "hello"
    assert called["title"] == "note"
    assert called["owner_user_id"] == UUID("10000000-0000-0000-0000-000000000001")


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


def test_chat_returns_persisted_assistant_turn_when_sidecar_is_corrupt(monkeypatch):
    from app.models.conversation import ChatRequest
    from app.pipelines.conversation_pipeline import ConversationPipeline

    class Session:
        id = "session_aabbccdd"
        total_messages = 1

    persisted = []

    def add_message(**kwargs):
        persisted.append(kwargs)
        return type("Message", (), {"id": f"msg_{len(persisted)}"})()

    monkeypatch.setattr("app.pipelines.conversation_pipeline.session_service.create_session", lambda: Session())
    monkeypatch.setattr("app.pipelines.conversation_pipeline.session_service.add_message", add_message)
    monkeypatch.setattr("app.pipelines.conversation_pipeline.llm_service.detect_save_intent", lambda _: {"wants_to_save": False})
    monkeypatch.setattr("app.pipelines.conversation_pipeline.context_builder.build", lambda **_: {"context": "ctx", "memory_ids_used": []})
    monkeypatch.setattr("app.pipelines.conversation_pipeline.context_builder.build_system_prompt", lambda: "system")
    monkeypatch.setattr("app.pipelines.conversation_pipeline.llm_service._call", lambda *_, **__: "answer")
    monkeypatch.setattr(
        "app.pipelines.conversation_pipeline.conversation_service.process_and_extract",
        lambda **_: (_ for _ in ()).throw(StorageCorruptionException("Extracted-memory data")),
    )

    result = ConversationPipeline().chat(ChatRequest(message="remember this"))

    assert result.answer == "answer"
    assert result.new_memories == 0
    assert any(item["role"].value == "assistant" for item in persisted)


def test_favorite_route_uses_singleton_binding(client, monkeypatch):
    class Storage:
        def set_favorite_owned(self, _db, owner_user_id, memory_id, is_favorite):
            assert owner_user_id == UUID("10000000-0000-0000-0000-000000000001")
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
    class Sessions:
        def get_session_owned(self, *_args):
            raise ResourceNotFoundException("Session")

    monkeypatch.setattr(chat_routes, "session_service", Sessions())
    result = client.get("/api/v1/sessions/session_deadbeef")
    assert result.status_code == 404
    assert result.json()["error"]["code"] == "resource_not_found"


def test_delete_session_removes_sidecar(client, isolated_sessions, monkeypatch):
    session = isolated_sessions.create_session()
    sidecar = isolated_sessions.sessions_dir / f"{session.id}_memories.json"
    sidecar.write_text("[]", encoding="utf-8")

    def delete_session_owned(_db, _owner_user_id, session_id):
        return isolated_sessions.delete_session(session_id)

    monkeypatch.setattr(
        chat_routes,
        "session_service",
        type("Sessions", (), {"delete_session_owned": staticmethod(delete_session_owned)})(),
    )

    result = client.delete(f"/api/v1/sessions/{session.id}")
    assert result.status_code == 200
    assert not sidecar.exists()
    assert not (isolated_sessions.sessions_dir / f"{session.id}.json").exists()


def test_graph_routes_validate_depth_and_memory_ids(client, monkeypatch):
    class Graph:
        def get_related_owned(self, _db, _owner_user_id, memory_id, depth):
            if memory_id != "mem_1":
                raise ResourceNotFoundException("Memory")
            return []

        def add_edge_owned(self, _db, _owner_user_id, from_id, to_id, *args, **kwargs):
            if "mem_missing" in (from_id, to_id):
                raise ResourceNotFoundException("Memory")
            return True

    monkeypatch.setattr(search_routes, "graph_service", Graph())
    invalid_depth = client.get("/api/v1/memories/mem_1/related?depth=99")
    missing_memory = client.post("/api/v1/memories/link", json={"from_id": "mem_1", "to_id": "mem_missing"})
    self_link = client.post("/api/v1/memories/link", json={"from_id": "mem_1", "to_id": "mem_1"})
    assert invalid_depth.status_code == 422
    assert missing_memory.status_code == 404
    assert self_link.status_code == 400
    assert self_link.json()["error"]["code"] == "invalid_request"


def test_graph_corruption_is_preserved_and_never_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "graph_dir", tmp_path)
    graph = GraphService()
    corrupt_content = "{not-json"
    graph.edges_path.write_text(corrupt_content, encoding="utf-8")

    with pytest.raises(StorageCorruptionException):
        graph.add_edge("mem_1", "mem_2")
    with pytest.raises(StorageCorruptionException):
        graph.remove_edge("mem_1", "mem_2")

    assert graph.edges_path.read_text(encoding="utf-8") == corrupt_content


def test_corrupt_session_sidecar_is_preserved_and_returns_storage_error(client, isolated_sessions, monkeypatch):
    session = isolated_sessions.create_session()
    sidecar = isolated_sessions.sessions_dir / f"{session.id}_memories.json"
    corrupt_content = "{not-json"
    sidecar.write_text(corrupt_content, encoding="utf-8")
    memory = ExtractedMemory(session_id=session.id, memory_type=MemoryType.FACT, content="fact")

    with pytest.raises(StorageCorruptionException):
        isolated_sessions.save_extracted_memory(session.id, memory)
    assert sidecar.read_text(encoding="utf-8") == corrupt_content

    def get_extracted_memories_owned(_db, _owner_user_id, session_id):
        return isolated_sessions.get_extracted_memories(session_id)

    monkeypatch.setattr(
        chat_routes,
        "session_service",
        type("Sessions", (), {"get_extracted_memories_owned": staticmethod(get_extracted_memories_owned)})(),
    )
    result = client.get(f"/api/v1/sessions/{session.id}/memories")
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "storage_corrupt"


def test_session_list_skips_one_unreadable_regular_session_file(isolated_sessions, monkeypatch):
    readable = isolated_sessions.create_session()
    unreadable = isolated_sessions.create_session()
    original_load = isolated_sessions._load_json

    def load_json(path):
        if path.name == f"{unreadable.id}.json":
            raise StorageException("Unable to read session data.")
        return original_load(path)

    monkeypatch.setattr(isolated_sessions, "_load_json", load_json)
    listed_ids = [session["id"] for session in isolated_sessions.list_sessions()]

    assert listed_ids == [readable.id]


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
    monkeypatch.setattr(service, "_perform_pinned_get", lambda _: Redirect())
    with pytest.raises(UnsafeURLError):
        service._safe_get("https://public.example/")


class TrackableResponse:
    def __init__(self, *, content=b"", content_type="application/json", content_length=None, encoding="utf-8"):
        self.status_code = 200
        self.headers = {"Content-Type": content_type}
        if content_length is not None:
            self.headers["Content-Length"] = content_length
        self.encoding = encoding
        self.content = content
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield self.content

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    ("method", "response", "max_bytes"),
    [
        ("_oembed", TrackableResponse(content=b'{"title":"title"}'), 1024),
        ("_oembed", TrackableResponse(content=b"not-json"), 1024),
        ("_open_graph", TrackableResponse(content=b"<html><title>title</title></html>", content_length="invalid"), 1024),
        ("_open_graph", TrackableResponse(content=b"x" * 8, content_length="8"), 4),
        ("download_thumbnail", TrackableResponse(content=b"data", content_type="text/plain"), 4),
        ("download_thumbnail", TrackableResponse(content=b"x" * 8, content_type="image/png", content_length="8"), 4),
    ],
)
def test_pinned_responses_close_on_success_and_early_failures(tmp_path, monkeypatch, method, response, max_bytes):
    service = LinkService()
    monkeypatch.setattr(service, "_safe_get", lambda *_, **__: response)
    monkeypatch.setattr(settings, "max_remote_response_bytes", max_bytes)

    if method == "_oembed":
        service._oembed("https://public.example/page", "https://oembed.example", "generic")
    elif method == "_open_graph":
        if response.headers.get("Content-Length") == "8":
            with pytest.raises(UnsafeURLError):
                service._open_graph("https://public.example/page", "generic")
        else:
            service._open_graph("https://public.example/page", "generic")
    else:
        if response.headers.get("Content-Length") == "8":
            with pytest.raises(UnsafeURLError):
                service.download_thumbnail("https://public.example/image.png", str(tmp_path / "image.png"))
        else:
            service.download_thumbnail("https://public.example/image.png", str(tmp_path / "image.png"))

    assert response.closed is True


def test_safe_get_binds_each_redirect_to_its_validated_destination(monkeypatch):
    service = LinkService()
    first = service._ValidatedDestination(
        url="https://public.example/",
        scheme="https",
        hostname="public.example",
        port=443,
        ip_address="8.8.8.8",
        request_target="/",
        host_header="public.example",
    )
    second = service._ValidatedDestination(
        url="https://redirected.example/final",
        scheme="https",
        hostname="redirected.example",
        port=443,
        ip_address="1.1.1.1",
        request_target="/final",
        host_header="redirected.example",
    )
    resolved = []
    connected = []

    class Redirect:
        status_code = 302
        headers = {"Location": "https://redirected.example/final"}

        def close(self):
            return None

    class Final:
        status_code = 200
        headers = {}

    def resolve(url):
        resolved.append(url)
        return first if "public.example" in url else second

    def connect(destination):
        connected.append(destination)
        return Redirect() if len(connected) == 1 else Final()

    monkeypatch.setattr(service, "_resolve_public_destination", resolve)
    monkeypatch.setattr(service, "_perform_pinned_get", connect)
    result = service._safe_get("https://public.example/")

    assert result.status_code == 200
    assert [destination.ip_address for destination in connected] == ["8.8.8.8", "1.1.1.1"]
    assert resolved == ["https://public.example/", "https://redirected.example/final"]


def test_unsafe_thumbnail_is_skipped_without_failing_safe_page_metadata(monkeypatch):
    service = LinkService()

    class Page:
        status_code = 200
        headers = {}
        encoding = "utf-8"

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size):
            yield b'<html><head><meta property="og:title" content="Safe title"><meta property="og:image" content="http://private.test/image.jpg"></head></html>'

        def close(self):
            return None

    monkeypatch.setattr(service, "_safe_get", lambda _: Page())
    monkeypatch.setattr(
        service,
        "validate_url",
        lambda url: (_ for _ in ()).throw(UnsafeURLError()) if "private.test" in url else url,
    )
    metadata = service._open_graph("https://public.example/page", "generic")

    assert metadata["success"] is True
    assert metadata["title"] == "Safe title"
    assert metadata["thumbnail_url"] == ""


def test_link_ingestion_continues_when_thumbnail_download_is_unsafe(monkeypatch):
    pipeline = IngestPipeline()
    captured = {}
    monkeypatch.setattr(
        "app.pipelines.ingest_pipeline.link_service.extract_metadata",
        lambda _: {"platform": "generic", "title": "Safe title", "description": "desc", "author": "", "thumbnail_url": "http://private.test/image.jpg"},
    )
    monkeypatch.setattr(
        "app.pipelines.ingest_pipeline.link_service.download_thumbnail",
        lambda *_: (_ for _ in ()).throw(UnsafeURLError()),
    )
    monkeypatch.setattr(pipeline, "_process_content", lambda **kwargs: captured.update(kwargs) or response(FileType.LINK))

    result = pipeline.process_link("https://public.example/page")
    assert result.file_type is FileType.LINK
    assert captured["file_path"] == ""
    assert captured["is_image"] is False


def test_unexpected_error_uses_safe_response(client, monkeypatch):
    monkeypatch.setattr(search_routes.search_pipeline, "search_owned", lambda **_: (_ for _ in ()).throw(RuntimeError("secret filesystem path")))
    result = client.post("/api/v1/search", json={"query": "anything"})
    assert result.status_code == 500
    assert result.json()["error"]["code"] == "internal_error"
    assert "secret filesystem path" not in result.text
