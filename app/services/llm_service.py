from groq import Groq
import json
import re
from app.core.config import settings


class LLMService:

    def __init__(self):
        self.client = Groq(api_key=settings.groq_api_key)

        # Models
        self.smart_model = "llama-3.3-70b-versatile"
        self.fast_model = "llama-3.1-8b-instant"

        print("✅ Groq LLM جاهز!")

    # ============================================================
    # Helpers
    # ============================================================

    def _extract_json(self, text: str) -> dict:
        """Safe JSON extraction from model output"""
        text = text.strip()

        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError("No JSON found")
        except Exception:
            raise ValueError(f"Invalid JSON response: {text}")

    # ============================================================
    # 1. Content Analysis
    # ============================================================

    def analyze_content(self, text: str, file_name: str) -> dict:

        prompt = f"""
You are an expert AI content analyzer for a personal memory system.

RULES:
- Return ONLY valid JSON
- No markdown, no explanation
- Be precise and structured

INPUT:
File Name: {file_name}

Text:
{text[:3000]}

OUTPUT JSON FORMAT:
{{
  "summary": "2-3 clear sentences",
  "tags": ["max 6 tags"],
  "category": "technology|science|business|education|health|religion|personal|other",
  "key_concepts": ["max 5 concepts"],
  "importance_score": 0.0,
  "language": "ar|en|mixed",
  "content_type": "lecture|book|article|note|conversation|code|other",
  "cleaned_text": "cleaned version of text",
  "main_topic": "one sentence topic"
}}

SCORING:
0.0 = useless
0.5 = normal
0.8 = important
1.0 = critical knowledge
"""

        try:
            response = self.client.chat.completions.create(
                model=self.smart_model,
                messages=[{"role": "user", "content": prompt}]
            )

            raw = response.choices[0].message.content

            return self._extract_json(raw)

        except Exception as e:
            print(f"⚠️ Analysis failed: {e}")
            return self._default_analysis(text, file_name)

    # ============================================================
    # 2. Memory QA
    # ============================================================

    def answer_from_memories(self, query: str, memories: list) -> str:

        if not memories:
            return "معنديش أي معلومات عن ده في ذاكرتك."

        context = ""

        for i, m in enumerate(memories[:3]):
            context += f"""
Memory {i+1}:
File: {m.file_name}
Summary: {m.summary}
Text: {getattr(m, 'matched_text', '')[:400]}
--------------------
"""

        prompt = f"""
You are a personal AI memory assistant.

Answer the user based ONLY on provided memories.

Question:
{query}

Memories:
{context}

Rules:
- Be natural and helpful
- Mention file names when relevant
- If info is insufficient, say so clearly
"""

        try:
            response = self.client.chat.completions.create(
                model=self.smart_model,
                messages=[{"role": "user", "content": prompt}]
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"Error: {str(e)}"

    # ============================================================
    # 3. Fallback
    # ============================================================

    def _default_analysis(self, text, file_name):
        return {
            "summary": text[:200],
            "tags": [],
            "category": "other",
            "key_concepts": [],
            "importance_score": 0.5,
            "language": "mixed",
            "content_type": "other",
            "cleaned_text": text,
            "main_topic": file_name
        }


# ============================================================
# Singleton
# ============================================================

_llm_service = None

def get_llm_service():
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

llm_service = get_llm_service()