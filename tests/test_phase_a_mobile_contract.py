from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.routes import chat as chat_routes
from app.api.routes import search as search_routes
from app.auth.dependencies import get_current_user
from app.auth.tokens import create_access_token
from app.core.config import settings
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.models.conversation import ExtractedMemory, MessageRole
from app.services.file_delivery_service import OwnedMemoryFile, file_delivery_service
from app.services.ownership_service import OwnershipMismatchError, OwnershipResourceNotFoundError


OWNER_A = UUID("30000000-0000-0000-0000-000000000001")
OWNER_B = UUID("40000000-0000-0000-0000-000000000002")
TEST_JWT_SECRET = "phase-a-route-test-jwt-secret-with-at-least-thirty-two-characters"


class FakeDb:
    def __init__(self):
        self.users = {
            OWNER_A: User(id=OWNER_A, email="a@example.test", password_hash="$argon2id$test", display_name="A", is_active=True),
            OWNER_B: User(id=OWNER_B, email="b@example.test", password_hash="$argon2id$test", display_name="B", is_active=True),
        }

    def get(self, _model, user_id):
        return self.users.get(user_id)

    def rollback(self):
        pass


@pytest.fixture(autouse=True)
def configured_routes(monkeypatch):
    monkeypatch.setattr(settings, "jwt_signing_secret", TEST_JWT_SECRET)
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "access_token_lifetime_seconds", 900)
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    db = FakeDb()

    def request_db():
        yield db

    app.dependency_overrides[get_db] = request_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def auth_header(owner_id: UUID = OWNER_A) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(owner_id).value}"}


def test_memory_file_delivery_requires_bearer(client):
    response = client.get("/api/v1/memories/mem_a/file")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_memory_file_delivery_is_owner_scoped_and_safe(client, monkeypatch, tmp_path):
    owned_file = tmp_path / "owned.png"
    owned_file.write_bytes(b"\x89PNG\r\n\x1a\nfile")

    def resolve(_db, owner_user_id, memory_id):
        if owner_user_id == OWNER_B or memory_id == "missing":
            raise OwnershipMismatchError("foreign")
        return OwnedMemoryFile(path=owned_file, media_type="image/png", download_name=f"{memory_id}.png")

    monkeypatch.setattr(search_routes.file_delivery_service, "resolve_owned_memory_file", resolve)
    success = client.get("/api/v1/memories/mem_a/file", headers=auth_header())
    foreign = client.get("/api/v1/memories/mem_a/file", headers=auth_header(OWNER_B))
    missing = client.get("/api/v1/memories/missing/file", headers=auth_header())

    assert success.status_code == 200
    assert success.headers["content-type"].startswith("image/png")
    assert "mem_a.png" in success.headers.get("content-disposition", "")
    assert str(owned_file) not in success.text
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"error": {"code": "resource_not_found", "message": "Resource was not found."}}


def test_file_delivery_service_denies_missing_backing_file_and_owner_mismatch(monkeypatch):
    class Storage:
        def get_memory_owned(self, _db, _owner, memory_id):
            if memory_id == "foreign":
                raise OwnershipMismatchError("foreign")
            return [{"metadata": {"file_id": "not-a-uuid", "file_path": "/outside/unsafe.png"}}]

    monkeypatch.setattr("app.services.file_delivery_service.storage_service", Storage())
    with pytest.raises(Exception) as invalid_file:
        file_delivery_service.resolve_owned_memory_file(SimpleNamespace(), OWNER_A, "missing-file")
    with pytest.raises(Exception) as foreign_file:
        file_delivery_service.resolve_owned_memory_file(SimpleNamespace(), OWNER_A, "foreign")
    assert invalid_file.value.__class__.__name__ == foreign_file.value.__class__.__name__ == "ResourceNotFoundException"


def test_search_response_has_no_path_and_preserves_top_k(client, monkeypatch):
    item = SimpleNamespace(
        memory_id="mem_a",
        file_name="safe.png",
        summary="summary",
        matched_text="matched",
        tags=["tag"],
        created_at="2026-08-24T00:00:00",
        final_score=0.9,
        semantic_score=0.8,
        recency_score=0.7,
        importance_score=0.6,
    )
    monkeypatch.setattr(
        search_routes.search_pipeline,
        "search_owned",
        lambda **kwargs: {"query": kwargs["query"], "total": 1, "results": [item], "llm_answer": "answer"},
    )
    response = client.post("/api/v1/search", json={"query": "hello", "top_k": 20}, headers=auth_header())
    invalid = client.post("/api/v1/search", json={"query": "hello", "top_k": 21}, headers=auth_header())
    assert response.status_code == 200
    assert "file_path" not in response.json()["results"][0]
    assert invalid.status_code == 422
    assert invalid.json() == {"error": {"code": "validation_error", "message": "The request payload is invalid."}}


def test_session_cursor_pagination_is_deterministic_and_opaque(client, monkeypatch):
    sessions = [
        {"id": "session_b", "title": "B", "total_messages": 0, "created_at": "2026-01-01", "updated_at": "2026-01-03"},
        {"id": "session_a", "title": "A", "total_messages": 0, "created_at": "2026-01-01", "updated_at": "2026-01-03"},
        {"id": "session_c", "title": "C", "total_messages": 0, "created_at": "2026-01-01", "updated_at": "2026-01-02"},
    ]
    monkeypatch.setattr(chat_routes.session_service, "list_sessions_owned", lambda _db, _owner: sessions)
    first = client.get("/api/v1/sessions?limit=1", headers=auth_header())
    second = client.get(f"/api/v1/sessions?limit=1&cursor={first.json()['next_cursor']}", headers=auth_header())
    final = client.get(f"/api/v1/sessions?limit=1&cursor={second.json()['next_cursor']}", headers=auth_header())
    invalid = client.get("/api/v1/sessions?cursor=not-a-valid-cursor", headers=auth_header())

    assert [first.json()["sessions"][0]["id"], second.json()["sessions"][0]["id"], final.json()["sessions"][0]["id"]] == ["session_a", "session_b", "session_c"]
    assert final.json()["next_cursor"] is None
    assert str(OWNER_A) not in first.json()["next_cursor"]
    assert "/" not in first.json()["next_cursor"]
    assert invalid.status_code == 400


def test_session_message_and_sidecar_pagination(client, monkeypatch):
    messages = [
        SimpleNamespace(id="msg_b", role=MessageRole.USER, content="second", created_at="2026-01-01T00:00:00"),
        SimpleNamespace(id="msg_a", role=MessageRole.ASSISTANT, content="first", created_at="2026-01-01T00:00:00"),
    ]
    session = SimpleNamespace(id="session_a", title="t", total_messages=2, summary="", created_at="2026-01-01", messages=messages)
    memories = [
        ExtractedMemory(id="mem_b", session_id="session_a", memory_type="fact", content="b", importance=0.5, keywords=[], created_at="2026-01-01"),
        ExtractedMemory(id="mem_a", session_id="session_a", memory_type="fact", content="a", importance=0.5, keywords=[], created_at="2026-01-01"),
    ]
    monkeypatch.setattr(chat_routes.session_service, "get_session_owned", lambda _db, _owner, _id: session)
    monkeypatch.setattr(chat_routes.session_service, "get_extracted_memories_owned", lambda _db, _owner, _id: memories)
    detail = client.get("/api/v1/sessions/session_a?limit=1", headers=auth_header())
    sidecars = client.get("/api/v1/sessions/session_a/memories?limit=1", headers=auth_header())
    assert detail.status_code == sidecars.status_code == 200
    assert detail.json()["messages"][0]["id"] == "msg_a"
    assert detail.json()["next_cursor"]
    assert sidecars.json()["memories"][0]["id"] == "mem_a"
    assert sidecars.json()["next_cursor"]


def test_related_memories_use_bounded_stable_pages(client, monkeypatch):
    related = [
        {"memory_id": "mem_b", "relation_type": "auto", "score": 0.9},
        {"memory_id": "mem_a", "relation_type": "auto", "score": 0.9},
        {"memory_id": "mem_c", "relation_type": "auto", "score": 0.1},
    ]
    monkeypatch.setattr(search_routes.graph_service, "get_related_owned", lambda _db, _owner, _id, depth: related)
    first = client.get("/api/v1/memories/mem_root/related?page=1&page_size=2", headers=auth_header())
    second = client.get("/api/v1/memories/mem_root/related?page=2&page_size=2", headers=auth_header())
    invalid = client.get("/api/v1/memories/mem_root/related?page_size=0", headers=auth_header())
    assert [item["memory_id"] for item in first.json()["related"]] == ["mem_a", "mem_b"]
    assert [item["memory_id"] for item in second.json()["related"]] == ["mem_c"]
    assert invalid.status_code == 422


def test_openapi_documents_phase_a_contract_without_public_paths(client):
    document = client.get("/openapi.json").json()
    serialized = str(document)
    file_operation = document["paths"]["/api/v1/memories/{memory_id}/file"]["get"]
    sessions_operation = document["paths"]["/api/v1/sessions"]["get"]
    delete_session_operation = document["paths"]["/api/v1/sessions/{session_id}"]["delete"]
    link_upload_operation = document["paths"]["/api/v1/upload/link"]["post"]
    assert "file_path" not in serialized
    assert "HTTPBearer" in document["components"]["securitySchemes"]
    assert "image/png" in file_operation["responses"]["200"]["content"]
    assert "422" not in file_operation["responses"]
    assert "422" not in delete_session_operation["responses"]
    assert "415" not in link_upload_operation["responses"]
    assert any(parameter["name"] == "cursor" for parameter in sessions_operation["parameters"])
    assert "422" in sessions_operation["responses"]
    assert "ErrorResponse" in str(sessions_operation["responses"]["422"])


def test_validation_errors_remain_safe_for_json_and_pagination(client):
    malformed = client.post("/api/v1/search", data="{", headers={**auth_header(), "content-type": "application/json"})
    missing = client.post("/api/v1/search", json={}, headers=auth_header())
    invalid_pagination = client.get("/api/v1/sessions?limit=0", headers=auth_header())
    assert [response.status_code for response in [malformed, missing, invalid_pagination]] == [422, 422, 422]
    for response in [malformed, missing, invalid_pagination]:
        assert response.json() == {"error": {"code": "validation_error", "message": "The request payload is invalid."}}
