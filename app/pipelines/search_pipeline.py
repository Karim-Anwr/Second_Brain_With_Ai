from app.services.embedding_service import embedding_service
from app.services.storage_service import storage_service
from app.services.llm_service import llm_service
from app.models.memory import MemorySearchResult
from app.core.exceptions import EmbeddingFailedException, StorageException


class SearchPipeline:
    """
    مسؤول عن البحث الكامل.
    بياخد سؤال بالعربي أو الإنجليزي
    ويرجع أدق النتائج من الـ memories المحفوظة.
    """

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: dict = None,
    ) -> dict:

        print(f"\n🔍 بحث عن: '{query}'")

        # ── Step 1: Embed السؤال ──
        print("🔢 Step 1: Embedding السؤال...")
        query_embedding = embedding_service.generate(query)
        print(f"   ✅ Vector جاهز")

        # ── Step 2: دور في ChromaDB ──
        print("🗄️  Step 2: البحث في ChromaDB...")
        results = storage_service.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filters,
        )
        print(f"   ✅ لقى {len(results)} نتيجة")

        # ── Step 3: update access_count ──
        for result in results:
            try:
                storage_service.increment_access_count(result.memory_id)
            except Exception:
                pass

        # ── Step 4: LLM Answer ──
        llm_answer = None
        if results:
            print("🤖 Step 4: Gemini بيكتب الإجابة...")
            llm_answer = llm_service.answer_from_memories(
                query=query,
                memories=results,
            )
            print(f"   ✅ الإجابة جاهزة")

        return {
            "query":      query,
            "total":      len(results),
            "results":    results,
            "llm_answer": llm_answer,
        }

    def search_by_filter(
        self,
        category: str = None,
        is_favorite: bool = None,
        file_type: str = None,
        top_k: int = 10,
    ) -> dict:

        filters = {}
        if category:
            filters["category"] = category
        if is_favorite is not None:
            filters["is_favorite"] = is_favorite
        if file_type:
            filters["file_type"] = file_type

        if not filters:
            return {"query": "filter", "total": 0, "results": []}

        dummy_query = "show all memories"
        query_embedding = embedding_service.generate(dummy_query)

        results = storage_service.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filters,
        )

        return {
            "query":      f"filter: {filters}",
            "total":      len(results),
            "results":    results,
            "llm_answer": None,
        }


# Singleton
search_pipeline = SearchPipeline()