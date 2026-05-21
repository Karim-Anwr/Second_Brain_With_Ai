from app.services.embedding_service import embedding_service
from app.services.storage_service import storage_service
from app.services.llm_service import llm_service
from app.utils.arabic_normalizer import arabic_normalizer
from app.models.memory import MemorySearchResult


class SearchPipeline:

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: dict = None,
    ) -> dict:

        print(f"\n🔍 بحث عن: '{query}'")

        # ─────────────────────────────
        # Step 1: Normalize Query
        # ─────────────────────────────
        print("🔤 Step 1: تنظيف السؤال...")
        normalized_query = arabic_normalizer.normalize_query(query)

        # ─────────────────────────────
        # Step 2: Understand Query
        # ─────────────────────────────
        print("🧠 Step 2: فهم السؤال...")
        understanding = llm_service.understand_query(normalized_query)

        intent     = understanding.get("intent", query)
        keywords   = understanding.get("keywords", [])
        entities   = understanding.get("entities", [])
        expanded   = understanding.get("expanded_queries", [])
        category   = understanding.get("category", "any")

        # ─────────────────────────────
        # Filters
        # ─────────────────────────────
        search_filters = dict(filters) if filters else {}
        if category != "any":
            search_filters["category"] = category

        # ─────────────────────────────
        # Step 3: Embeddings
        # ─────────────────────────────
        all_queries = [normalized_query, intent] + expanded[:3]
        all_queries = list(dict.fromkeys(all_queries))

        embeddings = embedding_service.generate_batch(all_queries)

        # ─────────────────────────────
        # Step 4: Retrieval
        # ─────────────────────────────
        all_chunks = []

        for emb in embeddings:
            chunks = storage_service.search_raw_chunks(
                query_embedding=emb,
                top_k=15,
                filters=search_filters if search_filters else None,
            )
            all_chunks.extend(chunks)

        # ─────────────────────────────
        # Step 5: Merge
        # ─────────────────────────────
        merged = self._merge_chunks(all_chunks)

        # ─────────────────────────────
        # Step 6: Boosting
        # ─────────────────────────────
        boosted = self._apply_boost(merged, keywords, entities)

        boosted.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        top_chunks = boosted[:15]

        # ─────────────────────────────
        # Step 7: Rerank
        # ─────────────────────────────
        reranked = llm_service.rerank(
            query=query,
            intent=intent,
            chunks=top_chunks,
        )

        # ─────────────────────────────
        # Step 8: Final Results
        # ─────────────────────────────
        results = self._build_final_results(reranked, top_k)

        # ─────────────────────────────
        # Step 9: Access update
        # ─────────────────────────────
        for r in results:
            try:
                storage_service.increment_access_count(r.memory_id)
            except:
                pass

        # ─────────────────────────────
        # Step 10: LLM Answer
        # ─────────────────────────────
        llm_answer = llm_service.answer_from_memories(
            query=query,
            memories=results,
            user_intent=intent,
        )

        return {
            "query": query,
            "total": len(results),
            "results": results,
            "llm_answer": llm_answer,
        }

    # ============================================================
    # Merge
    # ============================================================

    def _merge_chunks(self, chunks: list[dict]) -> list[dict]:
        seen = {}

        for c in chunks:
            cid = c["metadata"].get("chunk_id", "")
            score = c.get("semantic_score", 0)

            if cid not in seen or score > seen[cid].get("semantic_score", 0):
                seen[cid] = c

        return list(seen.values())

    # ============================================================
    # Boost
    # ============================================================

    def _apply_boost(self, chunks, keywords, entities):

        for c in chunks:
            meta = c.get("metadata", {})
            text = c.get("chunk_text", "").lower()

            semantic = c.get("semantic_score", 0)
            importance = float(meta.get("importance_score", 0.5))
            recency = float(meta.get("recency_score", 0.5))
            access = int(meta.get("access_count", 0))
            fav = meta.get("is_favorite", "False") == "True"

            kw_boost = sum(0.02 for k in keywords if k.lower() in text)
            kw_boost = min(kw_boost, 0.10)

            ent_boost = sum(0.03 for e in entities if e.lower() in text)
            ent_boost = min(ent_boost, 0.05)

            popularity = min(access / 10.0, 1.0)

            score = (
                semantic * 0.55 +
                importance * 0.07 +
                recency * 0.03 +
                popularity * 0.05 +
                kw_boost +
                ent_boost
            )

            if fav:
                score = min(score + 0.08, 1.0)

            c["final_score"] = round(score, 4)
            c["keyword_boost"] = round(kw_boost, 4)
            c["entity_boost"] = round(ent_boost, 4)

        return chunks

    # ============================================================
    # Final build
    # ============================================================

    def _build_final_results(self, chunks, top_k):

        seen = {}

        for c in chunks:
            meta = c.get("metadata", {})
            mid = meta.get("memory_id", "")

            semantic = c.get("semantic_score", 0)
            rerank = c.get("rerank_score", 0.5)
            base = c.get("final_score", semantic)

            final = round(min(base * 0.75 + rerank * 0.25, 1.0), 4)

            if mid not in seen or final > seen[mid].final_score:
                seen[mid] = self._make_result(meta, c, semantic, final)

        results = list(seen.values())
        results.sort(key=lambda x: x.final_score, reverse=True)

        return results[:top_k]

    # ============================================================
    # FIXED (CRITICAL BUG HERE BEFORE)
    # ============================================================

    def _make_result(self, meta, chunk, semantic, final):

        return MemorySearchResult(
            memory_id=meta.get("memory_id", ""),
            file_name=meta.get("file_name", ""),
            file_path=meta.get("file_path", ""),
            summary=meta.get("summary", ""),
            matched_text=meta.get("chunk_text", ""),

            tags=(meta.get("tags", "") or "").split(",") if meta.get("tags") else [],
            keywords=(meta.get("keywords", "") or "").split(",") if meta.get("keywords") else [],
            entities=(meta.get("entities", "") or "").split(",") if meta.get("entities") else [],
            topics=(meta.get("topics", "") or "").split(",") if meta.get("topics") else [],

            category=meta.get("category", ""),
            language=meta.get("language", ""),
            content_type=meta.get("content_type", ""),

            created_at=meta.get("created_at", ""),

            final_score=final,
            semantic_score=round(semantic, 4),
            recency_score=float(meta.get("recency_score", 0.5)),
            importance_score=float(meta.get("importance_score", 0.5)),

            keyword_boost=chunk.get("keyword_boost", 0),
            entity_boost=chunk.get("entity_boost", 0),
            rerank_score=chunk.get("rerank_score", 0.5),
        )

    # ============================================================
    # Filter search
    # ============================================================

    def search_by_filter(self, category=None, is_favorite=None, file_type=None, top_k=10):

        filters = {}
        if category:
            filters["category"] = category
        if is_favorite is not None:
            filters["is_favorite"] = is_favorite
        if file_type:
            filters["file_type"] = file_type

        q_emb = embedding_service.generate("show memories")

        chunks = storage_service.search_raw_chunks(
            query_embedding=q_emb,
            top_k=top_k,
            filters=filters,
        )

        results = self._build_final_results(chunks, top_k)

        return {
            "query": str(filters),
            "total": len(results),
            "results": results,
            "llm_answer": None,
        }


search_pipeline = SearchPipeline()