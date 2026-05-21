from sentence_transformers import SentenceTransformer
from app.core.config import settings
from app.core.exceptions import EmbeddingFailedException
from app.utils.arabic_normalizer import arabic_normalizer


class EmbeddingService:
    """
    بيستخدم BGE-M3 — أقوى موديل multilingual مجاني.
    
    ليه BGE-M3؟
    - بيفهم العربي والإنجليزي مع بعض
    - أقوى من all-MiniLM في العربي بكتير
    - مجاني ويشتغل محلياً
    """

    def __init__(self):
        model_name = getattr(
            settings,
            'embedding_model',
            'BAAI/bge-m3'
        )
        print(f"جاري تحميل الموديل: {model_name}")
        self.model     = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        print(f"✅ الموديل جاهز! حجم الـ vector: {self.dimension}")

    def generate(self, text: str) -> list[float]:
        """
        بيحول نص واحد لـ vector.
        بينظف النص الأول قبل الـ embedding.
        """
        if not text or not text.strip():
            raise EmbeddingFailedException("النص فاضي")

        # normalize قبل الـ embedding
        normalized = arabic_normalizer.normalize(text)
        if not normalized.strip():
            normalized = text

        try:
            vector = self.model.encode(
                normalized,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            return vector.tolist()
        except Exception as e:
            raise EmbeddingFailedException(f"فشل الـ embedding: {e}")

    def generate_batch(
        self,
        texts: list[str],
        show_progress: bool = True,
    ) -> list[list[float]]:
        """
        بيحول list من النصوص لـ vectors.
        أسرع بكتير من generate واحد واحد.
        """
        if not texts:
            return []

        # normalize كل النصوص
        normalized = []
        for t in texts:
            n = arabic_normalizer.normalize(t)
            normalized.append(n if n.strip() else t)

        try:
            vectors = self.model.encode(
                normalized,
                normalize_embeddings=True,
                show_progress_bar=show_progress,
                batch_size=16 if len(texts) < 100 else 64,
            )
            return vectors.tolist()
        except Exception as e:
            raise EmbeddingFailedException(f"فشل الـ batch embedding: {e}")


# Singleton
_embedding_service = None

def get_embedding_service():
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

embedding_service = get_embedding_service()