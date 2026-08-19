from sentence_transformers import SentenceTransformer
from app.core.config import settings
from app.core.exceptions import EmbeddingFailedException
from app.utils.arabic_normalizer import arabic_normalizer


class EmbeddingService:
    """BGE-M3 embeddings, loaded only when a request actually needs them."""

    def __init__(self):
        self.model_name = settings.embedding_model
        self.model: SentenceTransformer | None = None
        self.dimension: int | None = None

    def _get_model(self) -> SentenceTransformer:
        if self.model is None:
            try:
                print(f"جاري تحميل الموديل: {self.model_name}")
                self.model = SentenceTransformer(self.model_name)
                self.dimension = self.model.get_sentence_embedding_dimension()
                print(f"✅ الموديل جاهز! حجم الـ vector: {self.dimension}")
            except Exception as exc:
                raise EmbeddingFailedException("Embedding model is unavailable.") from exc
        return self.model

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
            vector = self._get_model().encode(
                normalized,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            return vector.tolist()
        except EmbeddingFailedException:
            raise
        except Exception as exc:
            raise EmbeddingFailedException("Embedding generation failed.") from exc

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
            vectors = self._get_model().encode(
                normalized,
                normalize_embeddings=True,
                show_progress_bar=show_progress,
                batch_size=16 if len(texts) < 100 else 64,
            )
            return vectors.tolist()
        except EmbeddingFailedException:
            raise
        except Exception as exc:
            raise EmbeddingFailedException("Batch embedding generation failed.") from exc


# Singleton
_embedding_service: EmbeddingService | None = None

def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

embedding_service = get_embedding_service()
