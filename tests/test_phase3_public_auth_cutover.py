"""Route-level Phase 3 authorization cutover tests with fake request-scoped dependencies."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.routes import chat as chat_routes
from app.api.routes import search as search_routes
from app.api.routes import upload as upload_routes
from app.auth.dependencies import get_current_user
from app.auth.tokens import create_access_token
from app.core.config import settings
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.models.conversation import ChatResponse
from app.models.memory import Category, FileType, MemoryResponse
from app.services.ownership_service import OwnershipMismatchError, OwnershipResourceNotFoundError


OWNER_A = UUID("10000000-0000-0000-0000-000000000001")
OWNER_B = UUID("20000000-0000-0000-0000-000000000002")
TEST_JWT_SECRET = "phase-3-route-test-jwt-secret-with-at-least-thirty-two-characters"


class FakeDb:
    def __init__(self):
        self.users = {
            OWNER_A: User(id=OWNER_A, email="a@example.com", password_hash="$argon2id$test", display_name="A", is_active=True),
            OWNER_B: User(id=OWNER_B, email="b@example.com", password_hash="$argon2id$test", display_name="B", is_active=True),
        }
        self.commit_calls = 0
        self.rollback_calls = 0

    def get(self, _model, user_id):
        return self.users.get(user_id)

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1


@pytest.fixture(autouse=True)
def configured_routes(monkeypatch):
    monkeypatch.setattr(settings, "jwt_signing_secret", TEST_JWT_SECRET)
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "access_token_lifetime_seconds", 900)
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def db():
    return FakeDb()


@pytest.fixture
def client(db):
    def request_db():
        try:
            yield db
        except Exception:
            db.rollback()
            raise

    app.dependency_overrides[get_db] = request_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def auth_header(owner_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(owner_id).value}"}


def memory_response(memory_id: str = "mem_a") -> MemoryResponse:
    return MemoryResponse(
        memory_id=memory_id,
        file_name="note",
        file_type=FileType.TEXT,
        summary="summary",
        tags=[],
        category=Category.OTHER,
        importance=0.5,
        total_chunks=1,
    )


def _protected_requests(client: TestClient, headers: dict[str, str] | None):
    return [
        client.post("/api/v1/upload/link", json={"url": "https://example.test/path"}, headers=headers),
        client.post("/api/v1/upload", files={"file": ("upload.png", b"\x89PNG\r\n\x1a\n", "image/png")}, headers=headers),
        client.post("/api/v1/upload/text", json={"title": "note", "text": "hello"}, headers=headers),
        client.post("/api/v1/search", json={"query": "hello"}, headers=headers),
        client.post("/api/v1/memories/favorite", json={"memory_id": "mem_a", "is_favorite": True}, headers=headers),
        client.get("/api/v1/memories/mem_a/related", headers=headers),
        client.post("/api/v1/memories/link", json={"from_id": "mem_a", "to_id": "mem_b"}, headers=headers),
        client.post("/api/v1/chat", json={"message": "hello"}, headers=headers),
        client.get("/api/v1/sessions", headers=headers),
        client.get("/api/v1/sessions/session_aabbccdd", headers=headers),
        client.delete("/api/v1/sessions/session_aabbccdd", headers=headers),
        client.get("/api/v1/sessions/session_aabbccdd/memories", headers=headers),
    ]


@pytest.mark.parametrize("headers", [None, {"Authorization": "Bearer not-a-jwt"}])
def test_every_protected_route_rejects_missing_or_invalid_bearer_before_global_resource_access(client, monkeypatch, headers):
    monkeypatch.setattr(upload_routes.ingest_pipeline, "process_link", lambda *_args, **_kwargs: pytest.fail("global link called"))
    monkeypatch.setattr(upload_routes.ingest_pipeline, "process", lambda *_args, **_kwargs: pytest.fail("global file called"))
    monkeypatch.setattr(upload_routes.ingest_pipeline, "process_text", lambda *_args, **_kwargs: pytest.fail("global text called"))
    monkeypatch.setattr(search_routes.search_pipeline, "search", lambda *_args, **_kwargs: pytest.fail("global search called"))
    monkeypatch.setattr(chat_routes.conversation_pipeline, "chat", lambda *_args, **_kwargs: pytest.fail("global chat called"))

    responses = _protected_requests(client, headers)
    assert all(response.status_code == 401 for response in responses)
    assert all(response.json()["error"] == {"code": "authentication_failed", "message": "Invalid email or password."} for response in responses)


def test_authenticated_routes_propagate_token_owner_use_only_owned_primitives_and_commit_creates(client, db, monkeypatch):
    owners = []

    async def process_link_owned(route_db, owner_user_id, _url):
        owners.append(("link", route_db, owner_user_id))
        return memory_response("mem_link")

    async def save_upload_file_owned(route_db, owner_user_id, _file):
        owners.append(("file", route_db, owner_user_id))
        return "file_a", "/safe/owners/a/file_a.png", "image"

    def process_owned(db, owner_user_id, **_kwargs):
        owners.append(("file-memory", db, owner_user_id))
        return memory_response("mem_file")

    def process_text_owned(route_db, owner_user_id, _text, _title):
        owners.append(("text", route_db, owner_user_id))
        return memory_response("mem_text")

    def search_owned(db, owner_user_id, **_kwargs):
        owners.append(("search", db, owner_user_id))
        item = SimpleNamespace(
            memory_id="mem_a", file_name="note", file_path="", summary="summary", matched_text="private",
            tags=[], created_at="now", final_score=0.9, semantic_score=0.9, recency_score=1.0, importance_score=0.5,
        )
        return {"query": "hello", "total": 1, "results": [item], "llm_answer": "answer"}

    class Storage:
        def set_favorite(self, *_args, **_kwargs):
            pytest.fail("global favorite called")

        def set_favorite_owned(self, route_db, owner_user_id, memory_id, _is_favorite):
            owners.append(("favorite", route_db, owner_user_id))
            return memory_id == "mem_a"

    class Graph:
        def get_related(self, *_args, **_kwargs):
            pytest.fail("global graph traversal called")

        def add_edge(self, *_args, **_kwargs):
            pytest.fail("global graph link called")

        def get_related_owned(self, route_db, owner_user_id, memory_id, depth):
            owners.append(("related", route_db, owner_user_id))
            assert memory_id == "mem_a" and depth == 1
            return []

        def add_edge_owned(self, route_db, owner_user_id, from_id, to_id, relation_type, score):
            owners.append(("link-graph", route_db, owner_user_id))
            assert (from_id, to_id, relation_type, score) == ("mem_a", "mem_b", "manual", 1.0)
            return True

    class Sessions:
        def list_sessions(self, *_args, **_kwargs):
            pytest.fail("global session list called")

        def get_session(self, *_args, **_kwargs):
            pytest.fail("global session access called")

        def delete_session(self, *_args, **_kwargs):
            pytest.fail("global session delete called")

        def get_extracted_memories(self, *_args, **_kwargs):
            pytest.fail("global sidecar access called")

        def list_sessions_owned(self, route_db, owner_user_id):
            owners.append(("sessions", route_db, owner_user_id))
            return []

        def get_session_owned(self, route_db, owner_user_id, session_id):
            owners.append(("session", route_db, owner_user_id))
            return SimpleNamespace(id=session_id, title="chat", total_messages=0, summary="", created_at="now", messages=[])

        def delete_session_owned(self, route_db, owner_user_id, _session_id):
            owners.append(("delete-session", route_db, owner_user_id))
            return True

        def get_extracted_memories_owned(self, route_db, owner_user_id, _session_id):
            owners.append(("sidecar", route_db, owner_user_id))
            return []

    def chat_owned(route_db, owner_user_id, _request):
        owners.append(("chat", route_db, owner_user_id))
        return ChatResponse(session_id="session_aabbccdd", message_id="msg_a", answer="answer", memories_used=[], new_memories=0)

    monkeypatch.setattr(upload_routes.ingest_pipeline, "process_link_owned", process_link_owned)
    monkeypatch.setattr(upload_routes, "save_upload_file_owned", save_upload_file_owned)
    monkeypatch.setattr(upload_routes.ingest_pipeline, "process_owned", process_owned)
    monkeypatch.setattr(upload_routes.ingest_pipeline, "process_text_owned", process_text_owned)
    monkeypatch.setattr(upload_routes.link_service, "validate_url", lambda url: url)
    monkeypatch.setattr(search_routes.search_pipeline, "search_owned", search_owned)
    monkeypatch.setattr(search_routes, "storage_service", Storage())
    monkeypatch.setattr(search_routes, "graph_service", Graph())
    monkeypatch.setattr(chat_routes, "session_service", Sessions())
    monkeypatch.setattr(chat_routes.conversation_pipeline, "chat_owned", chat_owned)

    headers = auth_header(OWNER_A)
    assert client.post("/api/v1/upload/link", json={"url": "https://example.test/path"}, headers=headers).status_code == 200
    assert client.post("/api/v1/upload", files={"file": ("upload.png", b"\x89PNG\r\n\x1a\n", "image/png")}, headers=headers).status_code == 200
    assert client.post("/api/v1/upload/text", json={"title": "note", "text": "hello"}, headers=headers).status_code == 200
    assert client.post("/api/v1/search", json={"query": "hello"}, headers=headers).status_code == 200
    assert client.post("/api/v1/memories/favorite", json={"memory_id": "mem_a", "is_favorite": True}, headers=headers).status_code == 200
    assert client.get("/api/v1/memories/mem_a/related", headers=headers).status_code == 200
    assert client.post("/api/v1/memories/link", json={"from_id": "mem_a", "to_id": "mem_b"}, headers=headers).status_code == 200
    assert client.post("/api/v1/chat", json={"message": "hello"}, headers=headers).status_code == 200
    assert client.get("/api/v1/sessions", headers=headers).status_code == 200
    assert client.get("/api/v1/sessions/session_aabbccdd", headers=headers).status_code == 200
    assert client.delete("/api/v1/sessions/session_aabbccdd", headers=headers).status_code == 200
    assert client.get("/api/v1/sessions/session_aabbccdd/memories", headers=headers).status_code == 200

    assert {owner for _, _, owner in owners} == {OWNER_A}
    assert all(route_db is db for _, route_db, _ in owners)
    assert db.commit_calls == 4


def test_foreign_and_missing_owned_resources_share_one_404_envelope_and_never_become_500(client, monkeypatch):
    class Storage:
        def set_favorite_owned(self, _db, owner_user_id, memory_id, _is_favorite):
            if memory_id == "mem_a" and owner_user_id == OWNER_B:
                raise OwnershipMismatchError("foreign")
            raise OwnershipResourceNotFoundError("missing")

    class Graph:
        def get_related_owned(self, _db, owner_user_id, memory_id, depth):
            assert depth == 1
            if memory_id == "mem_a" and owner_user_id == OWNER_B:
                raise OwnershipMismatchError("foreign")
            raise OwnershipResourceNotFoundError("missing")

        def add_edge_owned(self, *_args, **_kwargs):
            raise OwnershipMismatchError("foreign")

    class Sessions:
        def get_session_owned(self, _db, _owner_user_id, _session_id):
            raise OwnershipMismatchError("foreign")

        def delete_session_owned(self, _db, _owner_user_id, _session_id):
            raise OwnershipMismatchError("foreign")

        def get_extracted_memories_owned(self, _db, _owner_user_id, _session_id):
            raise OwnershipMismatchError("foreign")

    def chat_owned(_db, _owner_user_id, _request):
        raise OwnershipMismatchError("foreign")

    monkeypatch.setattr(search_routes, "storage_service", Storage())
    monkeypatch.setattr(search_routes, "graph_service", Graph())
    monkeypatch.setattr(chat_routes, "session_service", Sessions())
    monkeypatch.setattr(chat_routes.conversation_pipeline, "chat_owned", chat_owned)

    headers = auth_header(OWNER_B)
    foreign = client.post("/api/v1/memories/favorite", json={"memory_id": "mem_a", "is_favorite": True}, headers=headers)
    missing = client.post("/api/v1/memories/favorite", json={"memory_id": "mem_missing", "is_favorite": True}, headers=headers)
    responses = [
        foreign,
        missing,
        client.get("/api/v1/memories/mem_a/related", headers=headers),
        client.post("/api/v1/memories/link", json={"from_id": "mem_a", "to_id": "mem_b"}, headers=headers),
        client.post("/api/v1/chat", json={"session_id": "session_aabbccdd", "message": "hello"}, headers=headers),
        client.get("/api/v1/sessions/session_aabbccdd", headers=headers),
        client.delete("/api/v1/sessions/session_aabbccdd", headers=headers),
        client.get("/api/v1/sessions/session_aabbccdd/memories", headers=headers),
    ]
    assert all(response.status_code == 404 for response in responses)
    assert all(response.json() == {"error": {"code": "resource_not_found", "message": "Resource was not found."}} for response in responses)
    assert "foreign" not in foreign.text


def test_failed_owner_creating_route_rolls_back_without_global_fallback(client, db, monkeypatch):
    def failing_text(_db, _owner_user_id, _text, _title):
        raise RuntimeError("owned persistence failed")

    monkeypatch.setattr(upload_routes.ingest_pipeline, "process_text", lambda *_args, **_kwargs: pytest.fail("global text called"))
    monkeypatch.setattr(upload_routes.ingest_pipeline, "process_text_owned", failing_text)

    response = client.post("/api/v1/upload/text", json={"title": "note", "text": "hello"}, headers=auth_header(OWNER_A))
    assert response.status_code == 500
    assert db.commit_calls == 0
    assert db.rollback_calls == 1


def test_auth_routes_remain_public_without_bearer(client):
    response = client.post("/api/v1/auth/login", json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
