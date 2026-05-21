import re
from dataclasses import dataclass


@dataclass
class Chunk:
    """
    chunk واحد فيه كل المعلومات المحتاجاها.
    """
    text:          str
    index:         int
    prev_context:  str = ""
    next_context:  str = ""
    keywords:      list = None

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


class SemanticChunker:
    """
    بيقسم النص بطريقة ذكية بتحافظ على المعنى.
    
    الفرق عن الـ chunking العادي:
    - مش بيقطع في نص الجملة
    - بيحافظ على الفقرات
    - بيضيف context من الـ chunks المجاورة
    - بيتعامل مع العربي والإنجليزي
    """

    def __init__(
        self,
        chunk_size: int = 500,
        overlap: int = 50,
        min_chunk_size: int = 50,
    ):
        self.chunk_size     = chunk_size
        self.overlap        = overlap
        self.min_chunk_size = min_chunk_size

    def chunk(self, text: str) -> list[Chunk]:
        """
        النقطة الرئيسية للـ chunking.
        """
        if not text or len(text.strip()) < self.min_chunk_size:
            return []

        # قسم لجمل أولاً
        sentences = self._split_to_sentences(text)
        if not sentences:
            return []

        # اجمع الجمل في chunks
        raw_chunks = self._merge_sentences(sentences)

        # ضيف context
        chunks = self._add_context(raw_chunks)

        return chunks

    def _split_to_sentences(self, text: str) -> list[str]:
        """
        بيقسم النص لجمل.
        بيتعامل مع العربي والإنجليزي.
        """
        # نقاط التقسيم
        pattern = r'(?<=[.!?؟।\n])\s+'

        sentences = re.split(pattern, text)

        # نظف وشيل الفاضي
        sentences = [s.strip() for s in sentences if s.strip()]

        # اجمع الجمل القصيرة جداً مع اللي بعدها
        merged = []
        buffer = ""

        for sent in sentences:
            buffer += " " + sent if buffer else sent
            if len(buffer.split()) >= 20:
                merged.append(buffer.strip())
                buffer = ""

        if buffer:
            merged.append(buffer.strip())

        return merged

    def _merge_sentences(self, sentences: list[str]) -> list[str]:
        """
        بيجمع الجمل في chunks بحجم مناسب.
        """
        chunks  = []
        current = []
        count   = 0

        for sent in sentences:
            words = sent.split()
            count += len(words)
            current.append(sent)

            if count >= self.chunk_size:
                chunks.append(' '.join(current))
                # overlap: خد آخر جملة أو اتنين للـ chunk الجاي
                overlap_sents = current[-2:] if len(current) > 2 else current[-1:]
                current = overlap_sents
                count   = sum(len(s.split()) for s in current)

        if current:
            text = ' '.join(current)
            if len(text.split()) >= self.min_chunk_size:
                chunks.append(text)

        return chunks

    def _add_context(self, raw_chunks: list[str]) -> list[Chunk]:
        """
        بيضيف الـ context من الـ chunks المجاورة.
        
        ليه؟
        عشان لو الـ chunk بيتكلم عن "ده"
        يعرف "ده" إيه من الـ chunk اللي قبله.
        """
        chunks = []

        for i, text in enumerate(raw_chunks):
            prev = raw_chunks[i - 1][:150] if i > 0 else ""
            nxt  = raw_chunks[i + 1][:150] if i < len(raw_chunks) - 1 else ""

            # استخرج keywords بسيطة
            keywords = self._extract_keywords(text)

            chunks.append(Chunk(
                text=text,
                index=i,
                prev_context=prev,
                next_context=nxt,
                keywords=keywords,
            ))

        return chunks

    def _extract_keywords(self, text: str) -> list[str]:
        """
        بيستخرج الكلمات المهمة من الـ chunk.
        """
        # شيل كلمات قصيرة
        words = text.split()
        keywords = [
            w for w in words
            if len(w) > 4 and not w.isdigit()
        ]
        # رجع أكثر 10 كلمات تكراراً
        from collections import Counter
        freq = Counter(keywords)
        return [w for w, _ in freq.most_common(10)]


# Singleton
semantic_chunker = SemanticChunker()