import google.generativeai as genai
from app.core.config import settings
from app.core.exceptions import SecondBrainException


class LLMService:
    """
    مسؤول عن التواصل مع Gemini API.
    بياخد النتائج من الـ search ويكتب إجابة طبيعية.
    """

    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash")
        print("✅ Gemini جاهز!")

    def answer_from_memories(
        self,
        query: str,
        memories: list,
    ) -> str:
        """
        بياخد سؤال المستخدم + النتائج من ChromaDB
        ويكتب إجابة طبيعية بالعربي.
        """

        # لو مفيش نتائج
        if not memories:
            return "معنديش أي معلومات عن ده في ذاكرتك."

        # جهز الـ context من الـ memories
        context = ""
        for i, memory in enumerate(memories[:3]):  # أحسن 3 بس
            context += f"""
الذاكرة {i+1}:
الملف: {memory.file_name}
التاريخ: {memory.created_at}
المحتوى: {memory.matched_text}
---"""

        # الـ prompt
        prompt = f"""أنت مساعد ذكي للذاكرة الشخصية.
مهمتك إنك تجاوب على سؤال المستخدم بناءً على المعلومات المحفوظة في ذاكرته.

سؤال المستخدم: {query}

المعلومات المحفوظة:
{context}

تعليمات:
- اجاوب بالعربي بشكل طبيعي ومفيد
- اذكر اسم الملف والتاريخ لو مناسب
- لو المعلومات مش كافية قول ده بصراحة
- متكررش المعلومات بالحرف — لخصها بأسلوبك
"""

        try:
            response = self.model.generate_content(prompt)
            return response.text

        except Exception as e:
            return f"حصل خطأ في الـ LLM: {str(e)}"


# Singleton
_llm_service = None

def get_llm_service():
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

llm_service = get_llm_service()