import base64
import json
from pathlib import Path
from groq import Groq
from app.core.config import settings


def encode_image(image_path: str) -> str:
    """حول الصورة لـ base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


class GroqVisionProvider:
    """
    بيستخدم Groq Vision لفهم الصور.
    موديل: llava-v1.5-7b-4096-preview
    مجاني وسريع.
    """

    def __init__(self):
        self.client = Groq(api_key=settings.groq_api_key)
        self.model  = "meta-llama/llama-4-scout-17b-16e-instruct"

    def analyze(self, image_path: str) -> dict:
        """
        بيبعت الصورة لـ Groq ويرجع تحليل كامل.
        """
        try:
            b64 = encode_image(image_path)
            ext = Path(image_path).suffix.lower()
            mime = {
                ".jpg":  "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png":  "image/png",
                ".webp": "image/webp",
            }.get(ext, "image/jpeg")

            prompt = """أنت نظام تحليل صور ذكي ومتخصص.
حلل الصورة دي بدقة وارجع JSON فقط بدون أي كلام تاني:

{
    "content_type": "movie_poster|anime|tv_show|game|meme|product|screenshot|document|chat|ui|celebrity|logo|advertisement|technology|book|other",
    "visual_summary": "وصف تفصيلي للصورة في 2-3 جمل",
    "title": "اسم الفيلم/المسلسل/المنتج لو موجود",
    "entities": ["شخصية1", "شخصية2"],
    "people": ["اسم شخص حقيقي لو موجود"],
    "brands": ["brand1", "brand2"],
    "products": ["product1"],
    "detected_media": ["اسم فيلم أو مسلسل أو لعبة"],
    "topics": ["topic1", "topic2", "topic3"],
    "semantic_labels": ["label1", "label2", "label3", "label4"],
    "franchise": "اسم الـ franchise لو موجود",
    "language_detected": "ar|en|other",
    "confidence_score": 0.9,
    "ocr_quality": "good|poor|none"
}

تعليمات مهمة:
- حلل كل حاجة في الصورة بدقة
- لو فيه شخصيات مشهورة اذكرها
- لو فيه brands أو logos اذكرها
- لو فيه نص في الصورة اذكره في visual_summary
- الـ semantic_labels مش أكتر من 8
- الـ confidence_score من 0.0 لـ 1.0"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{b64}"
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
                max_tokens=1000,
                temperature=0.1,
            )

            raw = response.choices[0].message.content.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]

            return json.loads(raw.strip())

        except Exception as e:
            print(f"⚠️ Vision analysis فشل: {e}")
            return self._default_result()

    def _default_result(self) -> dict:
        return {
            "content_type":    "other",
            "visual_summary":  "",
            "title":           "",
            "entities":        [],
            "people":          [],
            "brands":          [],
            "products":        [],
            "detected_media":  [],
            "topics":          [],
            "semantic_labels": [],
            "franchise":       "",
            "language_detected": "mixed",
            "confidence_score": 0.0,
            "ocr_quality":     "none",
        }


class VisionService:
    """
    الـ service الرئيسي للـ vision.
    بيدعم أكتر من provider.
    """

    def __init__(self):
        self.provider = GroqVisionProvider()
        print("✅ Vision Service جاهز!")

    def analyze_image(self, image_path: str) -> dict:
        """
        النقطة الرئيسية — بتاخد مسار صورة وبترجع تحليل كامل.
        """
        print(f"     Vision Analysis...")
        result = self.provider.analyze(image_path)
        print(f"    Content: {result.get('content_type')} | "
              f"Confidence: {result.get('confidence_score', 0):.2f}")
        return result

    def is_supported(self, file_type: str) -> bool:
        return file_type in ["image", "image/jpeg", "image/png", "image/webp"]


# Singleton
_vision_service = None

def get_vision_service():
    global _vision_service
    if _vision_service is None:
        _vision_service = VisionService()
    return _vision_service

vision_service = get_vision_service()