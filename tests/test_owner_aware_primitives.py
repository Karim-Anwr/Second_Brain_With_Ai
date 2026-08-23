"""Focused unit coverage for explicit-owner Phase 2 internal primitives."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.db.models.owned_resource import OwnedResourceKind
from app.models.conversation import MessageRole
from app.models.memory import FileType, Memory


OWNER_A = UUID("10000000-0000-0000-0000-000000000001")
OWNER_B = UUID("20000000-0000-0000-0000-000000000002")


class FakeAuthority:
    records: dict[tuple[str, str], UUID] = {}

    def __init__(self, _db):
        pass

    def register_resource(self, *, owner_user_id, resource_kind, resource_id):
        kind = resource_kind.value if hasattr(resource_kind, "value") else resource_kind
        key = (kind, resource_id)
        if key in self.records:
            raise ValueError("duplicate logical resource")
        self.records[key] = owner_user_id
        return SimpleNamespace(owner_user_id=owner_user_id, resource_kind=kind, resource_id=resource_id)

    def require_owned_resource(self, *, owner_user_id, resource_kind, resource_id):
        from app.services.ownership_service import OwnershipMismatchError, OwnershipResourceNotFoundError

        kind = resource_kind.value if hasattr(resource_kind, "value") else resource_kind
        owner = self.records.get((kind, resource_id))
        if owner is None:
            raise OwnershipResourceNotFoundError("missing")
        if owner != owner_user_id:
            raise OwnershipMismatchError("wrong owner")
        return SimpleNamespace(owner_user_id=owner, resource_kind=kind, resource_id=resource_id)


@pytest.fixture(autouse=True)
def clear_fake_authority():
    FakeAuthority.records = {}


def _memory(memory_id: str = "mem_owned") -> Memory:
    return Memory(
        id=memory_id,
        file_name="owned.txt",
        file_type=FileType.TEXT,
        file_path="",
        chunks=["owner-scoped content"],
        total_chunks=1,
    )


def test_owned_storage_writes_owner_metadata_and_scopes_first_raw_query(monkeypatch):
    import app.services.storage_service as module

    monkeypatch.setattr(module, "OwnershipService", FakeAuthority)

    class FakeCollection:
        def __init__(self):
            self.added = None
            self.where = None

        def add(self, **kwargs):
            self.added = kwargs

        def count(self):
            return 1

        def query(self, **kwargs):
            self.where = kwargs["where"]
            return {
                "documents": [["owner-scoped content"]],
                "metadatas": [[{"owner_user_id": str(OWNER_A), "memory_id": "mem_owned", "chunk_text": "owner-scoped content"}]],
                "distances": [[0.1]],
            }

    service = module.StorageService.__new__(module.StorageService)
    service.collection = FakeCollection()
    service.save_memory_owned(object(), OWNER_A, _memory(), [[0.1]], ["searchable"])
    assert service.collection.added["metadatas"][0]["owner_user_id"] == str(OWNER_A)

    chunks = service.search_raw_chunks_owned(object(), OWNER_A, [0.1], filters={"category": "other"})
    assert chunks[0]["metadata"]["owner_user_id"] == str(OWNER_A)
    assert service.collection.where == {
        "$and": [
            {"owner_user_id": {"$eq": str(OWNER_A)}},
            {"category": {"$eq": "other"}},
        ]
    }


def test_owned_raw_search_fails_closed_for_missing_or_wrong_registry_memory(monkeypatch):
    import app.services.storage_service as module

    monkeypatch.setattr(module, "OwnershipService", FakeAuthority)
    FakeAuthority.records[("memory", "mem_registered")] = OWNER_A
    FakeAuthority.records[("memory", "mem_wrong_owner")] = OWNER_B

    class FakeCollection:
        def count(self):
            return 3

        def query(self, **kwargs):
            self.where = kwargs["where"]
            return {
                "documents": [["registered", "missing", "wrong owner"]],
                "metadatas": [[
                    {"memory_id": "mem_registered", "owner_user_id": str(OWNER_A)},
                    {"memory_id": "mem_missing", "owner_user_id": str(OWNER_A)},
                    {"memory_id": "mem_wrong_owner", "owner_user_id": str(OWNER_A)},
                ]],
                "distances": [[0.1, 0.2, 0.3]],
            }

    service = module.StorageService.__new__(module.StorageService)
    service.collection = FakeCollection()
    monkeypatch.setattr(
        service,
        "search_raw_chunks",
        lambda **_kwargs: pytest.fail("owned raw search must not call legacy global retrieval"),
    )
    chunks = service.search_raw_chunks_owned(object(), OWNER_A, [0.1])
    assert [chunk["metadata"]["memory_id"] for chunk in chunks] == ["mem_registered"]
    assert service.collection.where == {"owner_user_id": {"$eq": str(OWNER_A)}}


def test_owned_raw_search_rejects_another_users_registered_memory(monkeypatch):
    import app.services.storage_service as module

    monkeypatch.setattr(module, "OwnershipService", FakeAuthority)
    FakeAuthority.records[("memory", "mem_a")] = OWNER_A

    class FakeCollection:
        def count(self):
            return 1

        def query(self, **_kwargs):
            return {
                "documents": [["A only"]],
                "metadatas": [[{"memory_id": "mem_a", "owner_user_id": str(OWNER_B)}]],
                "distances": [[0.1]],
            }

    service = module.StorageService.__new__(module.StorageService)
    service.collection = FakeCollection()
    assert service.search_raw_chunks_owned(object(), OWNER_B, [0.1]) == []


def test_owned_storage_rejects_wrong_owner_before_projection_mutation(monkeypatch):
    import app.services.storage_service as module
    from app.services.ownership_service import OwnershipMismatchError

    monkeypatch.setattr(module, "OwnershipService", FakeAuthority)
    FakeAuthority.records[("memory", "mem_a")] = OWNER_A
    service = module.StorageService.__new__(module.StorageService)
    service.collection = SimpleNamespace(get=lambda **_kwargs: pytest.fail("Chroma must not be queried"))

    with pytest.raises(OwnershipMismatchError):
        service.get_memory_owned(object(), OWNER_B, "mem_a")

    with pytest.raises(OwnershipMismatchError):
        service.set_favorite_owned(object(), OWNER_B, "mem_a", True)


def test_owned_storage_cleans_only_current_projection_when_chroma_write_fails(monkeypatch):
    import app.services.storage_service as module

    monkeypatch.setattr(module, "OwnershipService", FakeAuthority)

    class FailingCollection:
        def __init__(self):
            self.deleted_where = None

        def add(self, **_kwargs):
            raise RuntimeError("projection unavailable")

        def delete(self, *, where):
            self.deleted_where = where

    service = module.StorageService.__new__(module.StorageService)
    service.collection = FailingCollection()
    with pytest.raises(module.StorageException):
        service.save_memory_owned(object(), OWNER_A, _memory("mem_failure"), [[0.1]])
    assert service.collection.deleted_where == {
        "$and": [
            {"owner_user_id": {"$eq": str(OWNER_A)}},
            {"memory_id": {"$eq": "mem_failure"}},
        ]
    }


def test_owner_aware_search_uses_owned_raw_retrieval_before_rerank(monkeypatch):
    import app.pipelines.search_pipeline as module

    raw_calls = []

    class FakeStorage:
        def search_raw_chunks(self, **_kwargs):
            pytest.fail("owner-aware search must not call legacy global retrieval")

        def search_raw_chunks_owned(self, **kwargs):
            raw_calls.append(kwargs)
            return [{"metadata": {"memory_id": "mem_a", "owner_user_id": str(OWNER_A)}, "chunk_text": "A only", "semantic_score": 0.9}]

        def increment_access_count_owned(self, *_args):
            return None

    monkeypatch.setattr(module, "storage_service", FakeStorage())
    monkeypatch.setattr(module.embedding_service, "generate_batch", lambda _queries: [[0.1]])
    monkeypatch.setattr(module.llm_service, "understand_query", lambda _query: {"intent": "query", "keywords": [], "entities": [], "expanded_queries": [], "category": "any"})
    monkeypatch.setattr(module.llm_service, "rerank", lambda **kwargs: kwargs["chunks"])

    result = module.SearchPipeline().retrieve_owned(object(), OWNER_A, "query")
    assert [item.memory_id for item in result["results"]] == ["mem_a"]
    assert raw_calls[0]["owner_user_id"] == OWNER_A


def test_owned_file_paths_are_server_derived_and_traversal_cannot_escape_owner_root(monkeypatch, tmp_path):
    import app.utils.file_handler as module
    from app.services.ownership_service import OwnershipMismatchError

    monkeypatch.setattr(module, "OwnershipService", FakeAuthority)
    monkeypatch.setattr(module.settings, "upload_dir", tmp_path)
    FakeAuthority.records[("file", "file_a")] = OWNER_A
    owner_root = module._owner_upload_dir(str(OWNER_A))
    expected = owner_root / "file_a.txt"
    expected.write_text("owned", encoding="utf-8")
    assert module.resolve_upload_file_owned(object(), OWNER_A, "file_a", ".txt") == expected.resolve()
    with pytest.raises(OwnershipMismatchError):
        module.resolve_upload_file_owned(object(), OWNER_B, "file_a", ".txt")
    FakeAuthority.records[("file", "../escape")] = OWNER_A
    with pytest.raises(FileNotFoundError):
        module.resolve_upload_file_owned(object(), OWNER_A, "../escape", ".txt")


def test_owned_sessions_and_sidecars_require_parent_registry_scope(monkeypatch, tmp_path):
    import app.services.session_service as module
    from app.services.ownership_service import OwnershipMismatchError

    monkeypatch.setattr(module, "OwnershipService", FakeAuthority)
    service = module.SessionService.__new__(module.SessionService)
    service.sessions_dir = tmp_path
    service._lock = threading.RLock()
    session = service.create_session_owned(object(), OWNER_A)
    assert service.get_session_owned(object(), OWNER_A, session.id).id == session.id
    with pytest.raises(OwnershipMismatchError):
        service.add_message_owned(object(), OWNER_B, session.id, MessageRole.USER, "forged")
    with pytest.raises(OwnershipMismatchError):
        service.get_extracted_memories_owned(object(), OWNER_B, session.id)
    assert service.delete_session_owned(object(), OWNER_A, session.id) is True


def test_owned_graph_requires_same_owner_and_auto_link_never_calls_global_search(monkeypatch, tmp_path):
    import app.services.graph_service as module
    from app.services.ownership_service import OwnershipMismatchError

    monkeypatch.setattr(module, "OwnershipService", FakeAuthority)
    FakeAuthority.records[("memory", "mem_a")] = OWNER_A
    FakeAuthority.records[("memory", "mem_b")] = OWNER_A
    FakeAuthority.records[("memory", "mem_other")] = OWNER_B
    service = module.GraphService.__new__(module.GraphService)
    service._lock = threading.RLock()
    edges = []
    service._load_edges = lambda: list(edges)
    service._save_edges = lambda value: edges.__setitem__(slice(None), value)
    assert service.add_edge_owned(object(), OWNER_A, "mem_a", "mem_b") is True
    assert edges[0]["owner_user_id"] == str(OWNER_A)
    with pytest.raises(OwnershipMismatchError):
        service.add_edge_owned(object(), OWNER_A, "mem_a", "mem_other")

    class FakeStorage:
        def search_raw_chunks(self, **_kwargs):
            pytest.fail("owned auto-link must not call global search")

        def search_raw_chunks_owned(self, **kwargs):
            assert kwargs["owner_user_id"] == OWNER_A
            return [{"metadata": {"memory_id": "mem_b"}, "semantic_score": 0.9}]

    monkeypatch.setattr("app.services.storage_service.storage_service", FakeStorage())
    assert service.auto_link_owned(object(), OWNER_A, "mem_a", [0.1]) == 1


def test_owned_graph_traversal_excludes_unowned_or_cross_owner_neighbors(monkeypatch):
    import app.services.graph_service as module

    monkeypatch.setattr(module, "OwnershipService", FakeAuthority)
    FakeAuthority.records[("memory", "mem_a")] = OWNER_A
    FakeAuthority.records[("memory", "mem_b")] = OWNER_A
    FakeAuthority.records[("memory", "mem_other")] = OWNER_B
    service = module.GraphService.__new__(module.GraphService)
    service._load_edges = lambda: [
        {"from": "mem_a", "to": "mem_b", "owner_user_id": str(OWNER_A), "score": 0.9},
        {"from": "mem_a", "to": "mem_other", "owner_user_id": str(OWNER_A), "score": 0.8},
    ]
    assert service.get_related_owned(object(), OWNER_A, "mem_a") == [
        {"memory_id": "mem_b", "relation_type": "semantic", "score": 0.9}
    ]


def test_owned_ingestion_and_conversation_retrieval_propagate_explicit_owner_without_global_fallback(monkeypatch):
    import app.pipelines.ingest_pipeline as ingest_module
    import app.services.conversation_service as conversation_module

    saved = []
    linked = []
    monkeypatch.setattr(ingest_module.embedding_service, "generate_batch", lambda _texts: [[0.1]])
    monkeypatch.setattr(ingest_module.storage_service, "save_memory", lambda **_kwargs: pytest.fail("legacy save must not run"))
    monkeypatch.setattr(ingest_module.storage_service, "save_memory_owned", lambda **kwargs: saved.append(kwargs))
    monkeypatch.setattr(ingest_module.graph_service, "auto_link_owned", lambda **kwargs: linked.append(kwargs) or 0)

    response = ingest_module.IngestPipeline().process_text_owned(object(), OWNER_A, "private text", "note")
    assert saved[0]["owner_user_id"] == OWNER_A
    assert linked[0]["owner_user_id"] == OWNER_A
    assert response.memory_id == saved[0]["memory"].id

    class FakeSearch:
        def retrieve(self, **_kwargs):
            pytest.fail("owned conversation retrieval must not call global search")

        def retrieve_owned(self, db, owner_user_id, query, top_k):
            assert db is not None and owner_user_id == OWNER_A and query == "private"
            return {"results": [SimpleNamespace(memory_id="mem_a", file_name="note", created_at="now", matched_text="private")]}

    monkeypatch.setattr("app.pipelines.search_pipeline.search_pipeline", FakeSearch())
    result = conversation_module.ConversationService().get_long_term_memory_owned(object(), OWNER_A, "private")
    assert result[0]["metadata"]["memory_id"] == "mem_a"


def test_owned_conversation_validates_parent_session_before_derived_memory(monkeypatch):
    import app.services.conversation_service as module
    from app.services.ownership_service import OwnershipMismatchError

    calls = []

    class FakeSessions:
        def get_session_owned(self, _db, owner_user_id, session_id):
            calls.append((owner_user_id, session_id))
            if owner_user_id != OWNER_A:
                raise OwnershipMismatchError("wrong owner")
            return SimpleNamespace(id=session_id)

    class FakeIngestion:
        def process_text_owned(self, db, owner_user_id, content, title):
            calls.append((db, owner_user_id, content, title))
            return SimpleNamespace(memory_id="mem_derived")

    monkeypatch.setattr(module, "session_service", FakeSessions())
    monkeypatch.setattr(module, "ingest_pipeline", FakeIngestion())
    service = module.ConversationService()
    assert service.save_as_memory_owned(object(), OWNER_A, "session_abcdef12", "private") == "mem_derived"
    with pytest.raises(OwnershipMismatchError):
        service.save_as_memory_owned(object(), OWNER_B, "session_abcdef12", "forged")


def test_owned_link_ingestion_propagates_owner_without_global_fallback(monkeypatch):
    import app.pipelines.ingest_pipeline as module

    saved = []
    linked = []

    monkeypatch.setattr(module.embedding_service, "generate_batch", lambda _texts: [[0.1]])
    monkeypatch.setattr(module.storage_service, "save_memory", lambda **_kwargs: pytest.fail("global save must not run"))
    monkeypatch.setattr(module.storage_service, "save_memory_owned", lambda **kwargs: saved.append(kwargs))
    monkeypatch.setattr(module.graph_service, "auto_link", lambda **_kwargs: pytest.fail("global graph must not run"))
    monkeypatch.setattr(module.graph_service, "auto_link_owned", lambda **kwargs: linked.append(kwargs) or 0)
    monkeypatch.setattr(module.IngestPipeline, "process_link", lambda *_args: pytest.fail("global link path must not run"))
    monkeypatch.setattr(
        module.IngestPipeline,
        "_build_link_content",
        lambda _self, _url: ({"platform": "generic", "title": "Owner A link", "thumbnail_url": ""}, "owner-only content"),
    )

    response = asyncio.run(module.IngestPipeline().process_link_owned(object(), OWNER_A, "https://example.test/a"))
    assert response.memory_id == saved[0]["memory"].id
    assert saved[0]["owner_user_id"] == OWNER_A
    assert linked[0]["owner_user_id"] == OWNER_A

    asyncio.run(module.IngestPipeline().process_link_owned(object(), OWNER_B, "https://example.test/b"))
    assert [entry["owner_user_id"] for entry in saved] == [OWNER_A, OWNER_B]
    assert [entry["owner_user_id"] for entry in linked] == [OWNER_A, OWNER_B]


def test_owned_link_thumbnail_uses_owned_file_primitive_and_failure_stops_memory_projection(monkeypatch, tmp_path):
    import app.pipelines.ingest_pipeline as module

    observed = []

    def download_thumbnail(_url, path):
        Path(path).write_bytes(b"\xff\xd8\xffthumbnail")
        return True

    async def save_owned_file(db, owner_user_id, upload):
        observed.append((db, owner_user_id, await upload.read()))
        return "file_a", str(tmp_path / "owners" / str(owner_user_id) / "file_a.jpg"), "image"

    monkeypatch.setattr(module.link_service, "download_thumbnail", download_thumbnail)
    monkeypatch.setattr(module, "save_upload_file_owned", save_owned_file)
    thumbnail = asyncio.run(
        module.IngestPipeline()._save_link_thumbnail_owned(
            db=object(), owner_user_id=OWNER_A, thumbnail_url="https://example.test/image.jpg"
        )
    )
    assert thumbnail.endswith("file_a.jpg")
    assert observed[0][1:] == (OWNER_A, b"\xff\xd8\xffthumbnail")

    async def failing_owned_file(*_args):
        raise RuntimeError("file persistence failed")

    monkeypatch.setattr(module, "save_upload_file_owned", failing_owned_file)
    monkeypatch.setattr(module.storage_service, "save_memory_owned", lambda **_kwargs: pytest.fail("memory must not project"))
    monkeypatch.setattr(
        module.IngestPipeline,
        "_build_link_content",
        lambda _self, _url: ({"platform": "generic", "title": "Owner B link", "thumbnail_url": "https://example.test/image.jpg"}, "B content"),
    )
    with pytest.raises(RuntimeError, match="file persistence failed"):
        asyncio.run(module.IngestPipeline().process_link_owned(object(), OWNER_B, "https://example.test/b"))
