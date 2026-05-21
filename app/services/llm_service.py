from groq import Groq
import json
from app.core.config import settings


class LLMService:

    def __init__(self):
        self.client      = Groq(api_key=settings.groq_api_key)
        self.smart_model = "llama-3.3-70b-versatile"
        self.fast_model  = "llama-3.1-8b-instant"
        print("✅ Groq LLM جاهز!")

    def _call(self, prompt: str, fast: bool = False) -> str:
        """
        Helper مركزي لكل الـ API calls.
        fast=True → يستخدم الموديل الأسرع والأرخص
        fast=False → يستخدم الأذكى
        """
        model = self.fast_model if fast else self.smart_model
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
        )
        return response.choices[0].message.content.strip()

    def _parse_json(self, raw: str) -> dict:
        """شيل الـ markdown وparse الـ JSON"""
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())

    # ============================================================
    # 1. Query Understanding
    # ============================================================

    def understand_query(self, query: str) -> dict:
        prompt = f"""أنت محلل استعلامات ذكي.
حلل السؤال ده وارجع JSON فقط بدون أي كلام تاني:

السؤال: {query}

{{
    "intent": "قصد المستخدم في جملة واحدة واضحة",
    "keywords": ["كلمة1", "كلمة2", "كلمة3"],
    "entities": ["اسم1", "اسم2"],
    "expanded_queries": [
        "صياغة تانية للسؤال",
        "English version if applicable",
        "مرادفات أو مصطلحات قريبة"
    ],
    "category": "technology|science|business|education|health|religion|personal|entertainment|sports|programming|finance|news|social|research|product|other",
    "language": "ar|en|mixed",
    "time_filter": "recent|old|any",
    "expected_answer_type": "document|fact|summary|list|any"
}}

تعليمات:
- الـ expanded_queries مش أكتر من 4
- الـ keywords مش أكتر من 6
- لو السؤال عربي ضيف النسخة الإنجليزية
- لو السؤال تقني ضيف المصطلحات الإنجليزية"""

        try:
            raw = self._call(prompt, fast=True)
            return self._parse_json(raw)
        except Exception as e:
            print(f"⚠️ Query understanding فشل: {e}")
            return {
                "intent":               query,
                "keywords":             query.split()[:5],
                "entities":             [],
                "expanded_queries":     [query],
                "category":             "any",
                "language":             "mixed",
                "time_filter":          "any",
                "expected_answer_type": "any",
            }

    # ============================================================
    # 2. Reranker
    # ============================================================

    def rerank(
        self,
        query: str,
        intent: str,
        chunks: list[dict],
    ) -> list[dict]:
        if not chunks:
            return []

        chunks_text = ""
        for i, chunk in enumerate(chunks[:10]):
            chunks_text += f"""
[{i}] من: {chunk['metadata'].get('file_name', 'غير معروف')}
{chunk.get('chunk_text', '')[:300]}
---"""

        prompt = f"""أنت خبير في تقييم مدى صلة النصوص بالأسئلة.

السؤال: {query}
القصد: {intent}

النصوص:
{chunks_text}

رتب النصوص من الأكثر صلة للأقل.
ارجع JSON فقط:
{{
    "ranked_indices": [2, 0, 4, 1, 3],
    "relevance_scores": {{
        "0": 0.9,
        "1": 0.3,
        "2": 0.95
    }},
    "reasoning": "سبب الترتيب في جملة واحدة"
}}"""

        try:
            raw     = self._call(prompt, fast=True)
            result  = self._parse_json(raw)
            indices = result.get("ranked_indices", list(range(len(chunks))))
            scores  = result.get("relevance_scores", {})

            reranked = []
            for idx in indices:
                if idx < len(chunks):
                    chunk = chunks[idx].copy()
                    chunk["rerank_score"] = float(
                        scores.get(str(idx), 0.5)
                    )
                    reranked.append(chunk)
            return reranked

        except Exception as e:
            print(f"⚠️ Reranking فشل: {e}")
            for chunk in chunks:
                chunk["rerank_score"] = chunk.get("semantic_score", 0.5)
            return chunks

    # ============================================================
    # 3. تحليل المحتوى
    # ============================================================

    def analyze_content(self, text: str, file_name: str) -> dict:
        prompt = f"""أنت محلل محتوى ذكي ومتخصص.
حلل النص ده بدقة وارجع JSON فقط:

اسم الملف: {file_name}
النص:
{text[:3000]}

{{
    "summary": "ملخص دقيق من 2-3 جمل",
    "main_topic": "الموضوع الرئيسي في جملة واحدة",
    "tags": ["tag1", "tag2", "tag3"],
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "entities": ["اسم شخص أو مكان أو منتج"],
    "topics": ["topic1", "topic2"],
    "category": "technology|science|business|education|health|religion|personal|entertainment|sports|programming|finance|news|social|research|product|other",
    "content_type": "محاضرة|كتاب|مقال|ملاحظات|حديث|أغنية|وصفة|كود|أخرى",
    "language": "ar|en|mixed",
    "importance_score": 0.8,
    "cleaned_text": "النص بعد تنظيف أخطاء الـ OCR وتحسينه",
    "semantic_labels": ["label1", "label2"]
}}

تعليمات:
- tags مش أكتر من 8
- keywords مش أكتر من 10
- entities مش أكتر من 5
- importance من 0.1 لـ 1.0
- صلح أخطاء OCR في cleaned_text
- لو النص عربي اكتب summary بالعربي"""

        try:
            raw = self._call(prompt, fast=False)
            return self._parse_json(raw)
        except Exception as e:
            print(f"⚠️ Content analysis فشل: {e}")
            return self._default_analysis(text, file_name)

    def _default_analysis(self, text: str, file_name: str) -> dict:
        sentences = [
            s.strip() for s in text.split('.')
            if len(s.strip()) > 20
        ]
        summary = '. '.join(sentences[:3])
        return {
            "summary":          summary or text[:200],
            "main_topic":       file_name,
            "tags":             [],
            "keywords":         [],
            "entities":         [],
            "topics":           [],
            "category":         "other",
            "content_type":     "أخرى",
            "language":         "mixed",
            "importance_score": 0.5,
            "cleaned_text":     text,
            "semantic_labels":  [],
        }

    # ============================================================
    # 4. الرد الإنساني
    # ============================================================

    def answer_from_memories(
        self,
        query: str,
        memories: list,
        user_intent: str = "",
    ) -> str:
        if not memories:
            return (
                "😊 ما لقيتش حاجة عن ده في ذاكرتك.\n"
                "جرب ترفع محتوى عنه الأول!"
            )

        context = ""
        for i, memory in enumerate(memories[:3]):
            context += f"""
📄 [{i+1}] {memory.file_name}
📅 {memory.created_at[:10]}
📝 {memory.matched_text[:400]}
━━━━━━━━━━━━━━━"""

        prompt = f"""أنت مساعد ذكي اسمك "ذاكرة".
بتساعد المستخدم يلاقي معلوماته المحفوظة.

شخصيتك:
- ودود ومحترم وطبيعي
- بتتكلم زي صاحب مش زي روبوت
- بتستخدم emoji بشكل خفيف ومناسب
- بتحس المستخدم إنك فاهمه وبتساعده
- لو المعلومات ناقصة بتقوله بصراحة لطيفة
- مش بتكرر المعلومات بالحرف

سؤال المستخدم: {query}
قصده: {user_intent}

المعلومات اللي لقيناها:
{context}

اكتب رد طبيعي ومفيد:
- ابدأ بتأكيد إنك لقيت المعلومة
- اذكر اسم الملف بشكل طبيعي
- لخص المحتوى بأسلوبك أنت
- لو فيه أكتر من نتيجة رتبهم بوضوح
- اختم بعرض مساعدة إضافية"""

        try:
            return self._call(prompt, fast=False)
        except Exception as e:
            return f"😅 حصل خطأ صغير، جرب تاني: {str(e)}"


# Singleton
_llm_service = None

def get_llm_service():
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

llm_service = get_llm_service()