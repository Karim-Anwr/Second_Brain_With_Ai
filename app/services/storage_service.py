import hashlib
import chromadb
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import StorageException, DocumentNotFoundException
from app.core.legacy_paths import legacy_global_resource_path
from app.db.models.owned_resource import OwnedResourceKind
from app.models.memory import Memory, MemorySearchResult
from app.services.ownership_service import (
    OwnershipMismatchError,
    OwnershipResourceNotFoundError,
    OwnershipService,
)


class StorageService:
    """
    بيحفظ ويجيب الـ chunks من ChromaDB.

    Features:
    - chunk-level storage
    - metadata غني
    - hybrid scoring
    - deduplication
    """

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=str(settings.chroma_dir)
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"}
        )
        print(f"✅ ChromaDB جاهز — Collection: {settings.chroma_collection}")

    # ============================================================
    # Save Memory
    # ============================================================

    @legacy_global_resource_path("memory")
    def save_memory(
        self,
        memory: Memory,
        embeddings: list[list[float]],
        searchable_texts: list[str] = None,
    ) -> bool:
        try:
            ids = []
            documents = []
            metadatas = []

            for i, chunk in enumerate(memory.chunks):
                chunk_id = f"{memory.id}_chunk_{i}"

                doc = (
                    searchable_texts[i]
                    if searchable_texts and i < len(searchable_texts)
                    else chunk
                )

                ids.append(chunk_id)
                documents.append(doc)

                metadatas.append({
                    "memory_id": memory.id,
                    "chunk_id": chunk_id,
                    "chunk_index": i,
                    "total_chunks": memory.total_chunks,

                    "file_name": memory.file_name,
                    "file_type": memory.file_type.value,
                    "file_path": memory.file_path,
                    "created_at": memory.created_at,

                    "chunk_text": chunk,
                    "summary": memory.summary[:500],
                    "main_topic": getattr(memory, "main_topic", ""),
                    "language": memory.language.value,

                    "tags": ",".join(memory.tags),
                    "keywords": ",".join(getattr(memory, "keywords", [])),
                    "entities": ",".join(getattr(memory, "entities", [])),
                    "topics": ",".join(getattr(memory, "topics", [])),
                    "category": memory.category.value,
                    "content_type": getattr(memory, "content_type", ""),
                    "importance_score": memory.importance_score,

                    # Vision fields
                    "visual_summary": getattr(memory, "visual_summary", ""),
                    "detected_media": ",".join(getattr(memory, "detected_media", [])),
                    "brands": ",".join(getattr(memory, "brands", [])),
                    "products": ",".join(getattr(memory, "products", [])),
                    "people": ",".join(getattr(memory, "people", [])),
                    "franchise": getattr(memory, "franchise", ""),
                    "confidence_score": getattr(memory, "confidence_score", 0.0),
                    "ocr_quality": getattr(memory, "ocr_quality", "none"),

                    # Behavior
                    "access_count": memory.access_count,
                    "recency_score": memory.recency_score,
                    "is_favorite": str(memory.is_favorite),
                })

            self.collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            return True

        except Exception as e:
            raise StorageException(f"فشل حفظ الـ memory: {e}")

    def save_memory_owned(
        self,
        db: Session,
        owner_user_id: UUID,
        memory: Memory,
        embeddings: list[list[float]],
        searchable_texts: list[str] | None = None,
    ) -> bool:
        """Stage ownership then project a new logical memory into owner-scoped Chroma metadata.

        The caller owns the database transaction. If Chroma fails after ownership is
        staged, this method removes only chunks for the current memory/owner and
        re-raises so the caller can roll back the staged registry record.
        """
        ownership = OwnershipService(db)
        ownership.register_resource(
            owner_user_id=owner_user_id,
            resource_kind=OwnedResourceKind.MEMORY,
            resource_id=memory.id,
        )
        try:
            self._save_memory_with_owner(
                memory=memory,
                embeddings=embeddings,
                owner_user_id=owner_user_id,
                searchable_texts=searchable_texts,
            )
            return True
        except Exception:
            self._delete_owned_chunks(owner_user_id=owner_user_id, memory_id=memory.id)
            raise

    def _save_memory_with_owner(
        self,
        *,
        memory: Memory,
        embeddings: list[list[float]],
        owner_user_id: UUID,
        searchable_texts: list[str] | None,
    ) -> None:
        ids = []
        documents = []
        metadatas = []
        owner_value = str(owner_user_id)

        for i, chunk in enumerate(memory.chunks):
            chunk_id = f"{memory.id}_chunk_{i}"
            doc = searchable_texts[i] if searchable_texts and i < len(searchable_texts) else chunk
            ids.append(chunk_id)
            documents.append(doc)
            metadatas.append(
                {
                    "owner_user_id": owner_value,
                    "memory_id": memory.id,
                    "chunk_id": chunk_id,
                    "chunk_index": i,
                    "total_chunks": memory.total_chunks,
                    "file_name": memory.file_name,
                    "file_type": memory.file_type.value,
                    "file_path": memory.file_path,
                    "created_at": memory.created_at,
                    "chunk_text": chunk,
                    "summary": memory.summary[:500],
                    "main_topic": getattr(memory, "main_topic", ""),
                    "language": memory.language.value,
                    "tags": ",".join(memory.tags),
                    "keywords": ",".join(getattr(memory, "keywords", [])),
                    "entities": ",".join(getattr(memory, "entities", [])),
                    "topics": ",".join(getattr(memory, "topics", [])),
                    "category": memory.category.value,
                    "content_type": getattr(memory, "content_type", ""),
                    "importance_score": memory.importance_score,
                    "visual_summary": getattr(memory, "visual_summary", ""),
                    "detected_media": ",".join(getattr(memory, "detected_media", [])),
                    "brands": ",".join(getattr(memory, "brands", [])),
                    "products": ",".join(getattr(memory, "products", [])),
                    "people": ",".join(getattr(memory, "people", [])),
                    "franchise": getattr(memory, "franchise", ""),
                    "confidence_score": getattr(memory, "confidence_score", 0.0),
                    "ocr_quality": getattr(memory, "ocr_quality", "none"),
                    "access_count": memory.access_count,
                    "recency_score": memory.recency_score,
                    "is_favorite": str(memory.is_favorite),
                }
            )

        try:
            self.collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
        except Exception as exc:
            raise StorageException("Unable to persist the owned memory projection.") from exc

    @staticmethod
    def _owner_memory_where(owner_user_id: UUID, memory_id: str) -> dict:
        return {
            "$and": [
                {"owner_user_id": {"$eq": str(owner_user_id)}},
                {"memory_id": {"$eq": memory_id}},
            ]
        }

    def _delete_owned_chunks(self, *, owner_user_id: UUID, memory_id: str) -> None:
        try:
            self.collection.delete(where=self._owner_memory_where(owner_user_id, memory_id))
        except Exception:
            # Best-effort cleanup cannot replace the caller-owned database rollback.
            pass

    def _build_owned_filters(self, owner_user_id: UUID, filters: dict | None) -> dict:
        owner_filter = {"owner_user_id": {"$eq": str(owner_user_id)}}
        additional_filter = self._build_filters(filters) if filters else None
        if additional_filter is None:
            return owner_filter
        return {"$and": [owner_filter, additional_filter]}

    def search_raw_chunks_owned(
        self,
        db: Session,
        owner_user_id: UUID,
        query_embedding: list[float],
        top_k: int = 20,
        filters: dict | None = None,
    ) -> list[dict]:
        """Query Chroma with the owner condition in the first raw retrieval."""
        try:
            count = self.collection.count()
            if count == 0:
                return []
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, count),
                where=self._build_owned_filters(owner_user_id, filters),
                include=["documents", "metadatas", "distances"],
            )
            ownership = OwnershipService(db)
            authorized_memory_ids: dict[str, bool] = {}
            chunks = []
            for doc, metadata, distance in zip(
                results["documents"][0], results["metadatas"][0], results["distances"][0]
            ):
                memory_id = metadata.get("memory_id")
                if not isinstance(memory_id, str) or not memory_id:
                    continue
                if memory_id not in authorized_memory_ids:
                    try:
                        ownership.require_owned_resource(
                            owner_user_id=owner_user_id,
                            resource_kind=OwnedResourceKind.MEMORY,
                            resource_id=memory_id,
                        )
                    except (OwnershipResourceNotFoundError, OwnershipMismatchError):
                        authorized_memory_ids[memory_id] = False
                    else:
                        authorized_memory_ids[memory_id] = True
                if not authorized_memory_ids[memory_id]:
                    continue
                chunks.append(
                    {
                        "document": doc,
                        "metadata": metadata,
                        "semantic_score": max(0.0, 1 - distance),
                        "chunk_text": metadata.get("chunk_text", doc),
                    }
                )
            return chunks
        except Exception as exc:
            raise StorageException("Unable to perform owner-scoped raw search.") from exc

    def get_memory_owned(self, db: Session, owner_user_id: UUID, memory_id: str) -> list[dict]:
        """Resolve a logical memory only after registry and owner-scoped Chroma checks."""
        OwnershipService(db).require_owned_resource(
            owner_user_id=owner_user_id,
            resource_kind=OwnedResourceKind.MEMORY,
            resource_id=memory_id,
        )
        try:
            results = self.collection.get(
                where=self._owner_memory_where(owner_user_id, memory_id),
                include=["documents", "metadatas"],
            )
        except Exception as exc:
            raise StorageException("Unable to resolve the owned memory projection.") from exc
        if not results.get("ids"):
            raise DocumentNotFoundException("Memory")
        return [
            {"id": chunk_id, "document": document, "metadata": metadata}
            for chunk_id, document, metadata in zip(
                results["ids"], results.get("documents", []), results.get("metadatas", [])
            )
        ]

    def set_favorite_owned(self, db: Session, owner_user_id: UUID, memory_id: str, is_favorite: bool) -> bool:
        chunks = self.get_memory_owned(db, owner_user_id, memory_id)
        for chunk in chunks:
            metadata = dict(chunk["metadata"])
            metadata["is_favorite"] = str(is_favorite)
            self.collection.update(ids=[chunk["id"]], metadatas=[metadata])
        return True

    def increment_access_count_owned(self, db: Session, owner_user_id: UUID, memory_id: str) -> None:
        chunks = self.get_memory_owned(db, owner_user_id, memory_id)
        for chunk in chunks:
            metadata = dict(chunk["metadata"])
            metadata["access_count"] = int(metadata.get("access_count", 0)) + 1
            self.collection.update(ids=[chunk["id"]], metadatas=[metadata])

    # ============================================================
    # Search
    # ============================================================

    @legacy_global_resource_path("memory")
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict = None,
    ) -> list[MemorySearchResult]:

        try:
            where = self._build_filters(filters) if filters else None

            n_results = min(top_k * 3, 40)
            count = self.collection.count()

            if count == 0:
                return []

            n_results = min(n_results, count)

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )

            seen = {}

            for doc, meta, distance in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                memory_id = meta["memory_id"]
                semantic_score = max(0.0, 1 - distance)

                final_score = self._calculate_score(
                    semantic_score=semantic_score,
                    recency_score=float(meta.get("recency_score", 0.5)),
                    importance=float(meta.get("importance_score", 0.5)),
                    access_count=int(meta.get("access_count", 0)),
                    is_favorite=meta.get("is_favorite", "False") == "True",
                )

                result = self._make_result(
                    meta, doc, semantic_score, final_score
                )

                if memory_id not in seen or final_score > seen[memory_id].final_score:
                    seen[memory_id] = result

            final = list(seen.values())
            final.sort(key=lambda x: x.final_score, reverse=True)

            return final[:top_k]

        except Exception as e:
            raise StorageException(f"فشل الـ search: {e}")

    # ============================================================
    # Raw chunks
    # ============================================================

    @legacy_global_resource_path("memory")
    def search_raw_chunks(
        self,
        query_embedding: list[float],
        top_k: int = 20,
        filters: dict = None,
    ) -> list[dict]:

        try:
            where = self._build_filters(filters) if filters else None

            count = self.collection.count()
            if count == 0:
                return []

            n_results = min(top_k, count)

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )

            chunks = []

            for doc, meta, distance in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                chunks.append({
                    "document": doc,
                    "metadata": meta,
                    "semantic_score": max(0.0, 1 - distance),
                    "chunk_text": meta.get("chunk_text", doc),
                })

            return chunks

        except Exception as e:
            raise StorageException(f"فشل الـ raw search: {e}")

    # ============================================================
    # Scoring
    # ============================================================

    def _calculate_score(
        self,
        semantic_score: float,
        recency_score: float,
        importance: float,
        access_count: int,
        is_favorite: bool,
    ) -> float:

        popularity = min(access_count / 10.0, 1.0)

        score = (
            semantic_score * 0.55 +
            recency_score * 0.20 +
            importance * 0.15 +
            popularity * 0.10
        )

        if is_favorite:
            score = min(score + 0.10, 1.0)

        return round(score, 4)

    # ============================================================
    # Result builder
    # ============================================================

    def _make_result(
        self,
        meta: dict,
        doc: str,
        semantic_score: float,
        final_score: float,
    ) -> MemorySearchResult:

        return MemorySearchResult(
            memory_id=meta["memory_id"],
            file_name=meta["file_name"],
            file_path=meta.get("file_path", ""),
            summary=meta.get("summary", ""),
            matched_text=meta.get("chunk_text", doc),
            tags=meta.get("tags", "").split(",") if meta.get("tags") else [],
            created_at=meta.get("created_at", ""),

            final_score=final_score,
            semantic_score=round(semantic_score, 4),
            recency_score=round(float(meta.get("recency_score", 0.5)), 4),
            importance_score=round(float(meta.get("importance_score", 0.5)), 4),

            visual_summary=meta.get("visual_summary", ""),
            content_type=meta.get("content_type", ""),
            detected_media=meta.get("detected_media", "").split(",") if meta.get("detected_media") else [],
            brands=meta.get("brands", "").split(",") if meta.get("brands") else [],
            people=meta.get("people", "").split(",") if meta.get("people") else [],
        )

    # ============================================================
    # Filters
    # ============================================================

    def _build_filters(self, filters: dict):
        if not filters:
            return None

        conditions = []

        for key in ["category", "language", "file_type", "content_type"]:
            if key in filters:
                conditions.append({key: {"$eq": filters[key]}})

        if "is_favorite" in filters:
            conditions.append({"is_favorite": {"$eq": str(filters["is_favorite"])}})

        if len(conditions) == 0:
            return None
        if len(conditions) == 1:
            return conditions[0]

        return {"$and": conditions}

    # ============================================================
    # Helpers
    # ============================================================

    @legacy_global_resource_path("memory")
    def increment_access_count(self, memory_id: str):
        try:
            results = self.collection.get(
                where={"memory_id": {"$eq": memory_id}},
                include=["metadatas"]
            )

            if not results["ids"]:
                return

            for chunk_id, meta in zip(results["ids"], results["metadatas"]):
                meta["access_count"] = int(meta.get("access_count", 0)) + 1

                self.collection.update(
                    ids=[chunk_id],
                    metadatas=[meta]
                )

        except Exception:
            pass

    @legacy_global_resource_path("memory")
    def get_total_memories(self) -> int:
        try:
            return self.collection.count()
        except:
            return 0

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

# ============================================================
# favorite
# ============================================================


    @legacy_global_resource_path("memory")
    def set_favorite(self, memory_id: str, is_favorite: bool) -> bool:
        """
        بيعلّم كل chunks الذكرى كـ favorite أو يشيلها.
        """
        try:
            results = self.collection.get(
                where={"memory_id": {"$eq": memory_id}},
                include=["metadatas"]
            )
            if not results["ids"]:
                return False

            for chunk_id, meta in zip(results["ids"], results["metadatas"]):
                meta["is_favorite"] = str(is_favorite)
                self.collection.update(
                    ids=[chunk_id],
                    metadatas=[meta]
                )
            return True

        except Exception as e:
            raise StorageException(f"فشل تحديث الـ favorite: {e}")

    @legacy_global_resource_path("memory")
    def memory_exists(self, memory_id: str) -> bool:
        """Check that at least one stored chunk belongs to a memory identifier."""
        try:
            results = self.collection.get(where={"memory_id": {"$eq": memory_id}})
            return bool(results.get("ids"))
        except Exception as exc:
            raise StorageException("Failed to verify the requested memory.") from exc
# ============================================================
# Singleton
# ============================================================

_storage_service = None


def get_storage_service():
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


storage_service = get_storage_service()
