from app.models.conversation import ChatMessage, ExtractedMemory, MessageRole
from app.services.conversation_service import conversation_service
from app.utils.arabic_normalizer import arabic_normalizer


class ContextBuilder:
    """
    بيبني الـ context الكامل للـ LLM من 4 مصادر:
    
    1. Short-Term  ← آخر N رسايل
    2. Long-Term   ← ذكريات قديمة من ChromaDB
    3. Episodic    ← ذكريات مستخرجة من الـ session
    4. Query       ← سؤال المستخدم الحالي
    """

    def build(
        self,
        session_id: str,
        user_query: str,
        top_k_memories: int = 3,
    ) -> dict:
        """
        بيرجع dict فيه كل الـ context جاهز للـ LLM.
        """

        print("🏗️  Context Builder...")

        # ════════════════════════════════
        # 1. Short-Term Memory
        # ════════════════════════════════
        recent_messages = conversation_service.get_short_term_memory(
            session_id=session_id,
            last_n=8,
        )
        print(f"   📝 Short-term: {len(recent_messages)} رسائل")

        # ════════════════════════════════
        # 2. Long-Term Memory
        # ════════════════════════════════
        long_term = conversation_service.get_long_term_memory(
            query=user_query,
            top_k=top_k_memories,
        )
        print(f"   🧠 Long-term: {len(long_term)} ذكريات")

        # ════════════════════════════════
        # 3. Episodic Memory
        # ════════════════════════════════
        episodic = conversation_service.get_episodic_memory(session_id)
        # خد أهم 5 بس
        episodic = sorted(
            episodic,
            key=lambda x: x.importance,
            reverse=True
        )[:5]
        print(f"   🎭 Episodic: {len(episodic)} ذكريات")

        # ════════════════════════════════
        # 4. بناء الـ Context النهائي
        # ════════════════════════════════
        context = self._format_context(
            recent_messages=recent_messages,
            long_term=long_term,
            episodic=episodic,
            user_query=user_query,
        )

        return {
            "context":          context,
            "recent_messages":  recent_messages,
            "long_term":        long_term,
            "episodic":         episodic,
            "memory_ids_used":  [
                m.get("metadata", {}).get("memory_id", "")
                for m in long_term
            ],
        }

    def _format_context(
        self,
        recent_messages: list[ChatMessage],
        long_term: list[dict],
        episodic: list[ExtractedMemory],
        user_query: str,
    ) -> str:
        """
        بيحول كل الـ context لـ string جاهز للـ LLM.
        """
        parts = []

        # ── Episodic Memory ──
        if episodic:
            parts.append("=== معلومات مهمة عن المستخدم ===")
            for mem in episodic:
                parts.append(
                    f"• [{mem.memory_type.value}] {mem.content}"
                )
            parts.append("")

        # ── Long-Term Memory ──
        if long_term:
            parts.append("=== ذكريات ذات صلة ===")
            for i, mem in enumerate(long_term):
                meta      = mem.get("metadata", {})
                file_name = meta.get("file_name", "غير معروف")
                chunk     = mem.get("chunk_text", "")[:300]
                date      = meta.get("created_at", "")[:10]
                parts.append(
                    f"[{i+1}] من: {file_name} ({date})\n{chunk}"
                )
            parts.append("")

        # ── Recent Conversation ──
        if recent_messages:
            parts.append("=== المحادثة الأخيرة ===")
            for msg in recent_messages:
                role = "أنت" if msg.role == MessageRole.USER else "ذاكرة"
                parts.append(f"{role}: {msg.content}")
            parts.append("")

        # ── Current Query ──
        parts.append(f"=== السؤال الحالي ===")
        parts.append(user_query)

        return "\n".join(parts)

    def build_system_prompt(self) -> str:
        """
        الـ system prompt الثابت للمساعد.
        """
        return """أنت "ذاكرة" — مساعد ذكي للذاكرة الشخصية.

شخصيتك:
- ودود وطبيعي زي صاحب
- بتتذكر كل حاجة المستخدم قالها
- بتربط المعلومات ببعض بذكاء
- بتستخدم emoji بشكل خفيف
- بتكون صريح لو مش عندك معلومة

قدراتك:
- تتذكر الملفات والصور المحفوظة
- تتذكر المحادثات السابقة
- تربط المعلومات الجديدة بالقديمة
- تقدر تلخص وتحلل

قواعد مهمة:
- لو مش عندك معلومة قول ده بصراحة
- استشهد بالملفات والتواريخ بشكل طبيعي
- متكررش نفس المعلومة أكتر من مرة
- لو السؤال عام أجب من معرفتك العامة"""


# Singleton
context_builder = ContextBuilder()