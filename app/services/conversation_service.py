from app.models.conversation import (
    ChatMessage, MessageRole, ExtractedMemory, MemoryType
)
from app.services.session_service import session_service
from app.services.memory_extractor_service import memory_extractor
from app.services.embedding_service import embedding_service
from app.services.storage_service import storage_service
from app.models.memory import Memory, FileType, Category, Language
from app.utils.arabic_normalizer import arabic_normalizer
from datetime import datetime
from app.pipelines.ingest_pipeline import ingest_pipeline

class ConversationService:
    """
    القلب الرئيسي للـ conversational memory.
    
    بيربط:
    - Session (المحادثة الحالية)
    - Long-term Memory (ChromaDB)
    - Memory Extraction (استخراج ذكريات)
    """

    # ============================================================
    # Short-Term Memory
    # ============================================================

    def get_short_term_memory(
        self,
        session_id: str,
        last_n: int = 8,
    ) -> list[ChatMessage]:
        """
        جيب آخر N رسايل من الـ session.
        دي الـ Short-Term Memory — بتديك السياق الحالي.
        """
        return session_service.get_recent_messages(
            session_id=session_id,
            last_n=last_n,
        )

    # ============================================================
    # Long-Term Memory
    # ============================================================

    def get_long_term_memory(
    self,
    query: str,
    top_k: int = 5,
) -> list[dict]:
        """
        دلوقتي بيستخدم نفس قوة search_pipeline
        بدل البحث الضعيف القديم.
        """
        from app.pipelines.search_pipeline import search_pipeline

        retrieval = search_pipeline.retrieve(query=query, top_k=top_k)
        results   = retrieval["results"]

        chunks = []
        for r in results:
            chunks.append({
                "metadata": {
                    "memory_id":  r.memory_id,
                    "file_name":  r.file_name,
                    "created_at": r.created_at,
                },
                "chunk_text": r.matched_text,
            })

        return chunks

    # ============================================================
    # save_as_memory
    # ============================================================
    def save_as_memory(
    self,
    session_id: str,
    content: str,
    title: str = "",
) -> str:
        """
        بيحفظ نص من المحادثة كـ memory حقيقية في ChromaDB.
        بيتنادى لما المستخدم يقول حاجة زي "احفظلي ده".
        """
        if not title:
            title = f"ذكرى من محادثة - {content[:40]}"

        result = ingest_pipeline.process_text(text=content, title=title)
        print(f"    اتحفظت كـ memory حقيقية: {result.memory_id}")
        return result.memory_id
    # ============================================================
    # Save Conversation Memory
    # ============================================================

    def save_conversation_memory(
        self,
        session_id: str,
        extracted: ExtractedMemory,
    ):
        """
        بيحفظ الذكرى المستخرجة في ChromaDB.
        عشان تبقى متاحة في الـ long-term memory.
        """
        try:
            # حول الذكرى لـ Memory object
            memory = Memory(
                file_name=f"conversation_{session_id}",
                file_type=FileType.NOTE,
                file_path="",
                file_size=len(extracted.content),
                file_hash="",
                raw_text=extracted.content,
                summary=extracted.summary or extracted.content,
                tags=extracted.keywords,
                keywords=extracted.keywords,
                entities=extracted.entities,
                topics=extracted.topics,
                category=Category.PERSONAL,
                importance_score=extracted.importance,
                language=Language.MIXED,
                chunks=[extracted.content],
                total_chunks=1,
                recency_score=1.0,
                content_type=extracted.memory_type.value,
            )

            # عمل embedding
            embedding = embedding_service.generate(extracted.content)

            # احفظ في ChromaDB
            storage_service.save_memory(
                memory=memory,
                embeddings=[embedding],
            )

            print(f"   💾 ذكرى محفوظة: {extracted.memory_type.value}")

        except Exception as e:
            print(f"   ⚠️ فشل حفظ الذكرى: {e}")

    # ============================================================
    # Process & Extract
    # ============================================================

    def process_and_extract(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
    ) -> list[ExtractedMemory]:
        """
        بعد كل رد:
        1. بيستخرج الذكريات المهمة
        2. بيحفظها في الـ session
        3. بيحفظها في ChromaDB لو مهمة
        """
        extracted_memories = []

        # جيب سياق المحادثة
        recent = self.get_short_term_memory(session_id, last_n=5)
        context = " | ".join([m.content[:100] for m in recent])

        # استخرج الذكريات
        result = memory_extractor.extract(
            user_message=user_message,
            assistant_response=assistant_response,
            session_context=context,
        )

        if result.get("should_store") and result.get("importance", 0) > 0.5:
            try:
                memory_type = MemoryType(
                    result.get("memory_type", "fact")
                )
            except:
                memory_type = MemoryType.FACT

            extracted = ExtractedMemory(
                session_id=session_id,
                memory_type=memory_type,
                content=result.get("content", user_message),
                summary=result.get("summary", ""),
                keywords=result.get("keywords", []),
                entities=result.get("entities", []),
                topics=result.get("topics", []),
                importance=float(result.get("importance", 0.5)),
            )

            # احفظ في الـ session
            session_service.save_extracted_memory(session_id, extracted)

            # احفظ في ChromaDB لو مهمة جداً
            if extracted.importance >= 0.7:
                self.save_conversation_memory(session_id, extracted)

            extracted_memories.append(extracted)

        return extracted_memories

    # ============================================================
    # Episodic Memory
    # ============================================================

    def get_episodic_memory(
        self,
        session_id: str,
    ) -> list[ExtractedMemory]:
        """
        جيب كل الذكريات المستخرجة من الـ session دي.
        دي الـ Episodic Memory — بتتذكر إيه اللي حصل.
        """
        return session_service.get_extracted_memories(session_id)

    # ============================================================
    # Session Summarization
    # ============================================================

    def summarize_session(
        self,
        session_id: str,
    ) -> str:
        """
        بيعمل ملخص للمحادثة كلها.
        بيتعمل تلقائي كل 20 رسالة.
        """
        recent = self.get_short_term_memory(session_id, last_n=20)
        if not recent:
            return ""

        messages_data = [
            {"role": m.role.value, "content": m.content}
            for m in recent
        ]

        result = memory_extractor.extract_batch(messages_data)
        summary = result.get("session_summary", "")

        if summary:
            session_service.update_session_summary(session_id, summary)

        return summary

# Singleton
_conversation_service = None

def get_conversation_service():
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service

conversation_service = get_conversation_service()