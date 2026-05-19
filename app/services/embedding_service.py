from sentence_transformers import SentenceTransformer
import numpy as np

from app.core.config import settings
from app.core.exceptions import EmbeddingFailedException


class EmbeddingService:
    """
    مسؤول عن تحويل النص لـ vectors.
    
    ليه class؟
    عشان الموديل بيتحمل مرة واحدة بس في الـ __init__
    مش كل مرة بنعمل embedding.
    تحميل الموديل 
    """

    def __init__(self, model_name: str = None):
        model_name = model_name or settings.embedding_model
        
        print(f"جاري تحميل الموديل: {model_name}")
        
        # بيتحمل مرة واحدة بس
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        
        print(f"الموديل جاهز! حجم الـ vector: {self.dimension}")

    # تحويل نص واحد لـ vector

    def generate(self, text: str) -> list[float]:
        """
        بيحول نص واحد لـ vector.
        
        بنستخدمه في الـ search —
        لما المستخدم يكتب سؤال، بنحوله لـ vector
        عشان نقارنه بالـ vectors المحفوظة.
        
        Returns:
            list of floats — مثلاً [0.23, -0.71, 0.45, ...]
        """
        if not text or not text.strip():
            raise EmbeddingFailedException("النص فاضي — مش هينفع نعمل embedding")

        try:
            vector = self.model.encode(text, normalize_embeddings=True)
            return vector.tolist()

        except Exception as e:
            raise EmbeddingFailedException(f"فشل الـ embedding: {str(e)}")

    # تحويل أكتر من نص مرة واحدة (أسرع)

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """
        بيحول list من النصوص لـ vectors مرة واحدة.
        
        ليه batch وماشيناش generate مرة مرة؟
        لأن الموديل أسرع بكتير لما بياخد
        كل النصوص مرة واحدة بدل ما ياخدهم واحد واحد.
        
        مثال:
        100 chunk × generate()       = 100 ثانية
        100 chunk × generate_batch() = 5 ثواني
        """
        if not texts:
            return []

        try:
            vectors = self.model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=True,   # بيوري progress bar
                batch_size=32             # بيعالج 32 نص في نفس الوقت
            )
            return vectors.tolist()

        except Exception as e:
            raise EmbeddingFailedException(f"فشل الـ batch embedding: {str(e)}")


# Singleton — بيتحمل مرة واحدة لما الـ app تبدأ
_embedding_service = None

def get_embedding_service():
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

embedding_service = get_embedding_service()