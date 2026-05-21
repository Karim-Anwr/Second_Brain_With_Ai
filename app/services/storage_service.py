import hashlib
import chromadb
from datetime import datetime
from app.core.config import settings
from app.core.exceptions import StorageException, DocumentNotFoundException
from app.models.memory import Memory, MemorySearchResult


class StorageService:
    """
    بيحفظ ويجيب الـ chunks من ChromaDB.
    
    التحسينات:
    - chunk-level storage (مش memory-level)
    - metadata غني
    - hybrid scoring
    - deduplication
    """

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.chroma_dir
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"}
        )
        print(f"✅ ChromaDB جاهز — Collection: {settings.chroma_collection}")

    # ============================================================
    # حفظ Memory
    # ============================================================

    def save_memory(
        self,
        memory: Memory,
        embeddings: list[list[float]],
        searchable_texts: list[str] = None,
    ) -> bool:
        """
        بيحفظ كل chunk كـ record منفصل في ChromaDB.
        
        الجديد: بيحفظ الـ searchable_text مع الـ chunk
        عشان الـ retrieval يبقى أدق.
        """
        try:
            ids        = []
            documents  = []
            metadatas  = []

            for i, chunk in enumerate(memory.chunks):
                chunk_id = f"{memory.id}_chunk_{i}"

                # الـ document اللي بيتحفظ هو الـ searchable_text
                # مش الـ chunk الخام
                doc = (
                    searchable_texts[i]
                    if searchable_texts and i < len(searchable_texts)
                    else chunk
                )

                ids.append(chunk_id)
                documents.append(doc)
                metadatas.append({
                    # ── Identity ──
                    "memory_id":    memory.id,
                    "chunk_id":     chunk_id,
                    "chunk_index":  i,
                    "total_chunks": memory.total_chunks,

                    # ── File Info ──
                    "file_name":    memory.file_name,
                    "file_type":    memory.file_type.value,
                    "file_path":    memory.file_path,
                    "created_at":   memory.created_at,

                    # ── Content ──
                    "chunk_text":   chunk,
                    "summary":      memory.summary[:500],
                    "main_topic":   getattr(memory, 'main_topic', ''),
                    "language":     memory.language.value,

                    # ── AI Fields ──
                    "tags":         ",".join(memory.tags),
                    "keywords":     ",".join(
                        getattr(memory, 'keywords', [])
                    ),
                    "entities":     ",".join(
                        getattr(memory, 'entities', [])
                    ),
                    "topics":       ",".join(
                        getattr(memory, 'topics', [])
                    ),
                    "category":     memory.category.value,
                    "content_type": getattr(memory, 'content_type', ''),
                    "importance_score": memory.importance_score,

                    # ── Behavior ──
                    "access_count":  memory.access_count,
                    "recency_score": memory.recency_score,
                    "is_favorite":   str(memory.is_favorite),
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

    # ============================================================
    # البحث
    # ============================================================

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict = None,
    ) -> list[MemorySearchResult]:
        """
        بيدور على أقرب chunks للـ query.
        """
        try:
            where = self._build_filters(filters) if filters else None

            n_results = min(top_k * 3, 40)
            count     = self.collection.count()
            if count == 0:
                return []
            n_results = min(n_results, count)

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )

            memories = []
            seen_memory_ids = {}

            for doc, meta, distance in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                memory_id      = meta["memory_id"]
                semantic_score = max(0.0, 1 - distance)

                final_score = self._calculate_score(
                    semantic_score=semantic_score,
                    recency_score=float(meta.get("recency_score", 0.5)),
                    importance=float(meta.get("importance_score", 0.5)),
                    access_count=int(meta.get("access_count", 0)),
                    is_favorite=meta.get("is_favorite", "False") == "True",
                )

                # لو نفس الـ memory اتجابت، خد الـ chunk الأعلى score
                if memory_id in seen_memory_ids:
                    existing = seen_memory_ids[memory_id]
                    if final_score > existing.final_score:
                        seen_memory_ids[memory_id] = self._make_result(
                            meta, doc, semantic_score, final_score
                        )
                    continue

                result = self._make_result(
                    meta, doc, semantic_score, final_score
                )
                seen_memory_ids[memory_id] = result

            # رتب بالـ final score
            memories = list(seen_memory_ids.values())
            memories.sort(key=lambda x: x.final_score, reverse=True)

            return memories[:top_k]

        except Exception as e:
            raise StorageException(f"فشل الـ search: {e}")

    def search_raw_chunks(
        self,
        query_embedding: list[float],
        top_k: int = 20,
        filters: dict = None,
    ) -> list[dict]:
        """
        بيرجع الـ raw chunks بدون deduplication.
        بيستخدمه الـ reranker.
        """
        try:
            where     = self._build_filters(filters) if filters else None
            count     = self.collection.count()
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
                    "document":       doc,
                    "metadata":       meta,
                    "semantic_score": max(0.0, 1 - distance),
                    "chunk_text":     meta.get("chunk_text", doc),
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
        """
        الأوزان الجديدة:
        semantic  55% ← الأهم
        recency   20%
        importance 15%
        popularity 10%
        """
        popularity  = min(access_count / 10.0, 1.0)

        score = (
            semantic_score * 0.55 +
            recency_score  * 0.20 +
            importance     * 0.15 +
            popularity     * 0.10
        )

        if is_favorite:
            score = min(score + 0.10, 1.0)

        return round(score, 4)

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
            tags=meta.get("tags", "").split(","),
            created_at=meta.get("created_at", ""),
            final_score=final_score,
            semantic_score=round(semantic_score, 4),
            recency_score=round(
                float(meta.get("recency_score", 0.5)), 4
            ),
            importance_score=round(
                float(meta.get("importance_score", 0.5)), 4
            ),
        )

    # ============================================================
    # Filters
    # ============================================================

    def _build_filters(self, filters: dict):
        conditions = []

        for key in ["category", "language", "file_type", "content_type"]:
            if key in filters:
                conditions.append({key: {"$eq": filters[key]}})

        if "is_favorite" in filters:
            conditions.append(
                {"is_favorite": {"$eq": str(filters["is_favorite"])}}
            )

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    # ============================================================
    # Helpers
    # ============================================================

    def increment_access_count(self, memory_id: str):
        try:
            results = self.collection.get(
                where={"memory_id": {"$eq": memory_id}},
                include=["metadatas"]
            )
            if not results["ids"]:
                return

            for chunk_id, meta in zip(
                results["ids"], results["metadatas"]
            ):
                meta["access_count"] = (
                    int(meta.get("access_count", 0)) + 1
                )
                self.collection.update(
                    ids=[chunk_id],
                    metadatas=[meta]
                )
        except Exception:
            pass

    def get_total_memories(self) -> int:
        try:
            return self.collection.count()
        except:
            return 0

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()


# Singleton
_storage_service = None

def get_storage_service():
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service

storage_service = get_storage_service()