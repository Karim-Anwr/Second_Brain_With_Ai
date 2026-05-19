import hashlib
import chromadb
from pathlib import Path
from datetime import datetime

from app.core.config import settings
from app.core.exceptions import StorageException, DocumentNotFoundException
from app.models.memory import Memory, MemorySearchResult


class StorageService:
    """
    مسؤول عن حفظ وجلب الـ memories.
    
    بيتعامل مع حاجتين:
    1. ChromaDB  ← الـ vectors والـ metadata
    2. File System ← الملفات الأصلية
    
    ليه فصلناهم؟
    لأن ChromaDB ممتازة في الـ vector search
    بس مش المفروض تحفظ فيها ملفات كبيرة.
    """

    def __init__(self):
        # اتصل بـ ChromaDB
        self.client = chromadb.PersistentClient(
            path=settings.chroma_dir
        )

        # جيب أو اعمل الـ collection
        self.collection = self.client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"}
            # cosine = بنقيس التشابه بالزاوية مش المسافة
            # الأنسب للـ text embeddings
        )

        print(f"✅ ChromaDB جاهز — Collection: {settings.chroma_collection}")

    # ============================================================
    # حفظ Memory جديدة
    # ============================================================

    def save_memory(self, memory: Memory, embeddings: list[list[float]]) -> bool:
        """
        بيحفظ الـ Memory في ChromaDB.
        
        كل chunk بيتحفظ كـ record منفصل مع:
        - الـ embedding بتاعه
        - الـ metadata بتاعت الـ memory كلها
        
        ليه كل chunk لوحده؟
        عشان الـ search يرجع الـ chunk الأدق
        مش الملف كله.
        """
        try:
            ids        = []
            documents  = []
            metadatas  = []

            for i, (chunk, embedding) in enumerate(
                zip(memory.chunks, embeddings)
            ):
                chunk_id = f"{memory.id}_chunk_{i}"

                ids.append(chunk_id)
                documents.append(chunk)
                metadatas.append({
                    # معلومات الـ memory
                    "memory_id":       memory.id,
                    "file_name":       memory.file_name,
                    "file_type":       memory.file_type.value,
                    "file_path":       memory.file_path,
                    "created_at":      memory.created_at,

                    # AI fields
                    "summary":         memory.summary,
                    "category":        memory.category.value,
                    "importance_score": memory.importance_score,
                    "language":        memory.language.value,
                    "tags":            ",".join(memory.tags),
                    # ليه join؟ ChromaDB مش بتدعم lists في الـ metadata

                    # Behavior fields
                    "access_count":    memory.access_count,
                    "is_favorite":     str(memory.is_favorite),
                    "recency_score":   memory.recency_score,

                    # Chunk info
                    "chunk_index":     i,
                    "total_chunks":    memory.total_chunks,
                })

            # حفظ في ChromaDB
            self.collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )

            return True

        except Exception as e:
            raise StorageException(f"فشل حفظ الـ memory: {str(e)}")

    # ============================================================
    # البحث
    # ============================================================

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict = None
    ) -> list[MemorySearchResult]:
        """
        بيدور على أقرب memories للـ query.
        
        الـ filters بتخليك تضيق البحث:
        مثال: ابحث بس في الـ technology category
        أو بس في آخر أسبوع
        """
        try:
            # جهز الـ where clause لو فيه filters
            where = self._build_filters(filters) if filters else None

            # ابحث في ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k * 2, 300),  # بنجيب ضعف العدد عشان بعدين نعمل ranking
                # بنجيب ضعف العدد عشان بعدين نعمل ranking
                # ونرجع أحسن top_k بس
                where=where,
                include=["documents", "metadatas", "distances"]
            )

            # حول النتائج لـ MemorySearchResult
            memories = []
            seen_memory_ids = set()
            # عشان ما نرجعش نفس الـ memory مرتين
            # (ممكن يجيب chunk_0 وchunk_1 من نفس الملف)

            for doc, meta, distance in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                memory_id = meta["memory_id"]

                # لو الـ memory دي اتضافت قبل كده، skip
                if memory_id in seen_memory_ids:
                    continue
                seen_memory_ids.add(memory_id)

                # حول الـ distance لـ similarity score
                # ChromaDB بترجع distance — كلما قل = أقرب
                semantic_score = 1 - distance

                # احسب الـ final score
                final_score = self._calculate_final_score(
                    semantic_score=semantic_score,
                    recency_score=float(meta.get("recency_score", 0.5)),
                    importance_score=float(meta.get("importance_score", 0.5)),
                    access_count=int(meta.get("access_count", 0)),
                    is_favorite=meta.get("is_favorite", "False") == "True",
                )

                memories.append(MemorySearchResult(
                    memory_id=memory_id,
                    file_name=meta["file_name"],
                    file_path=meta["file_path"],
                    summary=meta.get("summary", ""),
                    matched_text=doc,
                    tags=meta.get("tags", "").split(","),
                    created_at=meta["created_at"],
                    final_score=round(final_score, 3),
                    semantic_score=round(semantic_score, 3),
                    recency_score=round(float(meta.get("recency_score", 0.5)), 3),
                    importance_score=round(float(meta.get("importance_score", 0.5)), 3),
                ))

            # رتب بالـ final score
            memories.sort(key=lambda x: x.final_score, reverse=True)

            return memories[:top_k]

        except Exception as e:
            raise StorageException(f"فشل الـ search: {str(e)}")

    # ============================================================
    # Smart Ranking
    # ============================================================

    def _calculate_final_score(
        self,
        semantic_score: float,
        recency_score: float,
        importance_score: float,
        access_count: int,
        is_favorite: bool,
    ) -> float:
        """
        بيحسب الـ score النهائي من 4 عوامل.
        
        الأوزان دي ممكن تتعدل مع الوقت:
        - semantic  0.4  ← الأهم — مدى قرب المعنى
        - recency   0.3  ← الأحدث أهم
        - importance 0.2 ← AI قيّمها بأهمية عالية
        - popularity 0.1 ← بترجعلها كتير
        """
        # popularity من 0 لـ 1
        popularity = min(access_count / 10.0, 1.0)

        score = (
            semantic_score   * 0.50 +
            recency_score    * 0.25 +
            importance_score * 0.20 +
            popularity       * 0.05
        )

        # لو المستخدم عملها favorite — بوص دايماً
        if is_favorite:
            score = min(score + 0.15, 1.0)

        return score

    # ============================================================
    # Filters Builder
    # ============================================================

    def _build_filters(self, filters: dict) -> dict:
        """
        بيحول الـ filters لـ ChromaDB where clause.
        
        مثال:
        filters = {"category": "technology", "language": "ar"}
        →
        {"$and": [
            {"category": {"$eq": "technology"}},
            {"language": {"$eq": "ar"}}
        ]}
        """
        conditions = []

        if "category" in filters:
            conditions.append(
                {"category": {"$eq": filters["category"]}}
            )
        if "language" in filters:
            conditions.append(
                {"language": {"$eq": filters["language"]}}
            )
        if "file_type" in filters:
            conditions.append(
                {"file_type": {"$eq": filters["file_type"]}}
            )
        if "is_favorite" in filters:
            conditions.append(
                {"is_favorite": {"$eq": str(filters["is_favorite"])}}
            )

        if len(conditions) == 0:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    # ============================================================
    # Update — تحديث الـ access_count
    # ============================================================

    def increment_access_count(self, memory_id: str):
        """
        كل ما المستخدم يفتح memory، بنزود الـ access_count.
        ده بيخلي النظام يتعلم من سلوكك.
        """
        try:
            # جيب كل الـ chunks بتاعت الـ memory دي
            results = self.collection.get(
                where={"memory_id": {"$eq": memory_id}},
                include=["metadatas"]
            )

            if not results["ids"]:
                raise DocumentNotFoundException(
                    f"الـ memory مش موجودة: {memory_id}"
                )

            # حدّث كل chunk
            for chunk_id, meta in zip(
                results["ids"], results["metadatas"]
            ):
                meta["access_count"] = int(meta.get("access_count", 0)) + 1
                self.collection.update(
                    ids=[chunk_id],
                    metadatas=[meta]
                )

        except DocumentNotFoundException:
            raise
        except Exception as e:
            raise StorageException(f"فشل تحديث الـ access count: {str(e)}")

    # ============================================================
    # Helpers
    # ============================================================

    def get_total_memories(self) -> int:
        """كام memory محفوظة؟"""
        return self.collection.count()

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """
        بيحسب MD5 hash للملف.
        لو نفس الـ hash موجود = نفس الملف اترفع قبل كده.
        """
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