import json
from app.models.conversation import ExtractedMemory, MemoryType
from app.services.llm_service import llm_service


class MemoryExtractorService:
    """
    بيستخرج ذكريات مهمة من المحادثة تلقائياً.
    
    مثال:
    المستخدم: "أنا بشتغل على مشروع AI بالـ Python"
    المستخرج: {
        type: "project",
        content: "المستخدم بيشتغل على مشروع AI بالـ Python",
        importance: 0.85
    }
    """

    def extract(
        self,
        user_message: str,
        assistant_response: str,
        session_context: str = "",
    ) -> dict:
        """
        بيحلل الرسالة ويقرر:
        1. هل فيه معلومة تستحق الحفظ؟
        2. إيه نوعها؟
        3. كام أهميتها؟
        """
        prompt = f"""أنت نظام ذكي لاستخراج الذكريات المهمة من المحادثات.

رسالة المستخدم: {user_message}
رد المساعد: {assistant_response[:500]}
سياق المحادثة: {session_context[:300]}

حلل المحادثة وارجع JSON فقط:
{{
    "should_store": true,
    "importance": 0.85,
    "memory_type": "fact|preference|goal|task|relationship|conversation|personal_info|project|skill",
    "content": "الذكرى بشكل واضح ومفيد",
    "summary": "ملخص قصير",
    "keywords": ["كلمة1", "كلمة2"],
    "entities": ["اسم1", "اسم2"],
    "topics": ["topic1", "topic2"]
}}

قواعد الحفظ:
- احفظ لو فيه: معلومة شخصية، هدف، مشروع، مهارة، علاقة، تفضيل مهم
- لا تحفظ: كلام عام، أسئلة بسيطة، محادثة عابرة
- الـ importance من 0.0 لـ 1.0
- لو مفيش حاجة تستحق: should_store = false"""

        try:
            response = llm_service._call(prompt, fast=True)
            result   = llm_service._parse_json(response)
            return result
        except Exception as e:
            print(f"⚠️ Memory extraction فشل: {e}")
            return {"should_store": False}

    def extract_batch(
        self,
        messages: list[dict],
    ) -> list[dict]:
        """
        بيستخرج ذكريات من مجموعة رسايل.
        بيستخدمه لما بنعمل session summary.
        """
        if not messages:
            return []

        # جهز المحادثة
        conversation = ""
        for msg in messages[-10:]:  # آخر 10 رسايل بس
            role    = "المستخدم" if msg["role"] == "user" else "المساعد"
            conversation += f"{role}: {msg['content'][:200]}\n"

        prompt = f"""أنت نظام استخراج ذكريات ذكي.

المحادثة:
{conversation}

استخرج كل المعلومات المهمة وارجع JSON فقط:
{{
    "memories": [
        {{
            "memory_type": "fact|preference|goal|task|relationship|personal_info|project|skill",
            "content": "الذكرى بشكل واضح",
            "importance": 0.8,
            "keywords": ["كلمة1"],
            "entities": ["اسم1"]
        }}
    ],
    "session_summary": "ملخص المحادثة في 2-3 جمل"
}}

احفظ بس المعلومات المهمة وليها قيمة على المدى البعيد."""

        try:
            response = llm_service._call(prompt, fast=False)
            return llm_service._parse_json(response)
        except Exception as e:
            print(f"⚠️ Batch extraction فشل: {e}")
            return {"memories": [], "session_summary": ""}

    def score_importance(
        self,
        content: str,
        memory_type: str,
    ) -> float:
        """
        بيحسب أهمية الذكرى بناءً على نوعها.
        """
        base_scores = {
            "personal_info": 0.9,
            "goal":          0.85,
            "project":       0.85,
            "relationship":  0.8,
            "skill":         0.75,
            "preference":    0.7,
            "task":          0.65,
            "fact":          0.6,
            "conversation":  0.4,
        }
        return base_scores.get(memory_type, 0.5)


# Singleton
_memory_extractor = None

def get_memory_extractor():
    global _memory_extractor
    if _memory_extractor is None:
        _memory_extractor = MemoryExtractorService()
    return _memory_extractor

memory_extractor = get_memory_extractor()