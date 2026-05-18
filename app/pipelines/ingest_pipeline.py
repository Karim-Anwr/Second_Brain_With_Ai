import hashlib
from pathlib import Path
from datetime import datetime

from app.services.ocr_service import ocr_service
from app.services.embedding_service import embedding_service
from app.services.storage_service import storage_service
from app.models.memory import Memory, FileType, Category, Language, MemoryResponse
from app.utils.text_cleaner import clean_text, chunk_text
from app.core.config import settings
from app.core.exceptions import StorageException


class IngestPipeline:

    def process(
        self,
        file_path: str,
        file_name: str,
        file_type: str,
        file_size: int = 0,
    ) -> MemoryResponse:

        print(f"\n🚀 بدأ معالجة: {file_name}")

        print("📖 Step 1: OCR...")
        raw_text = ocr_service.extract_text(
            file_path=file_path,
            file_type=file_type
        )
        print(f"   ✅ استخرج {len(raw_text.split())} كلمة")

        print("🧹 Step 2: تنظيف النص...")
        cleaned_text = clean_text(raw_text)
        print(f"   ✅ النص اتنظف")

        print("✂️  Step 3: تقسيم لـ chunks...")
        chunks = chunk_text(
            text=cleaned_text,
            chunk_size=settings.max_chunk_size,
            overlap=settings.chunk_overlap
        )
        print(f"   ✅ {len(chunks)} chunk")

        print("🏷️  Step 4: تصنيف...")
        tags, category, importance, language, summary = \
            self._classify(cleaned_text, file_name)
        print(f"   ✅ Category: {category} | Tags: {tags[:3]}")

        file_hash = self._calculate_hash(file_path)

        print("🧠 Step 5: بناء الـ Memory Object...")
        memory = Memory(
            file_name=file_name,
            file_type=FileType(file_type),
            file_path=file_path,
            file_size=file_size,
            file_hash=file_hash,
            raw_text=cleaned_text,
            summary=summary,
            tags=tags,
            category=category,
            importance_score=importance,
            language=language,
            chunks=chunks,
            total_chunks=len(chunks),
            recency_score=1.0,
        )

        print("🔢 Step 6: Embedding...")
        embeddings = embedding_service.generate_batch(chunks)
        print(f"   ✅ {len(embeddings)} vector")

        print("💾 Step 7: حفظ في ChromaDB...")
        memory.chunk_ids = [
            f"{memory.id}_chunk_{i}"
            for i in range(len(chunks))
        ]
        storage_service.save_memory(
            memory=memory,
            embeddings=embeddings
        )
        total = storage_service.get_total_memories()
        print(f"   ✅ اتحفظ! إجمالي الـ memories: {total}")
        print(f"\n✨ خلص! Memory ID: {memory.id}")

        return MemoryResponse(
            memory_id=memory.id,
            file_name=memory.file_name,
            file_type=memory.file_type,
            summary=memory.summary,
            tags=memory.tags,
            category=memory.category,
            importance=memory.importance_score,
            total_chunks=memory.total_chunks,
            status="success"
        )

    def process_text(self, text: str, title: str) -> MemoryResponse:
        """
        بياخد نص مباشر بدل ملف — بيتخطى الـ OCR.
        """
        print(f"\n🚀 بدأ معالجة نص: {title}")

        cleaned_text = clean_text(text)

        chunks = chunk_text(
            text=cleaned_text,
            chunk_size=settings.max_chunk_size,
            overlap=settings.chunk_overlap
        )
        print(f"   ✅ {len(chunks)} chunk")

        tags, category, importance, language, summary = \
            self._classify(cleaned_text, title)

        memory = Memory(
            file_name=title,
            file_type=FileType.TEXT,
            file_path="",
            file_size=len(text),
            file_hash="",
            raw_text=cleaned_text,
            summary=summary,
            tags=tags,
            category=category,
            importance_score=importance,
            language=language,
            chunks=chunks,
            total_chunks=len(chunks),
            recency_score=1.0,
        )

        embeddings = embedding_service.generate_batch(chunks)

        memory.chunk_ids = [
            f"{memory.id}_chunk_{i}"
            for i in range(len(chunks))
        ]
        storage_service.save_memory(memory=memory, embeddings=embeddings)

        print(f"✨ خلص! Memory ID: {memory.id}")

        return MemoryResponse(
            memory_id=memory.id,
            file_name=memory.file_name,
            file_type=memory.file_type,
            summary=memory.summary,
            tags=memory.tags,
            category=memory.category,
            importance=memory.importance_score,
            total_chunks=memory.total_chunks,
            status="success"
        )

    def _classify(self, text: str, file_name: str):
        text_lower = text.lower()
        words      = text_lower.split()

        tech_keywords = [
            "python", "code", "api", "machine learning", "ai",
            "data", "model", "neural", "deep learning", "backend",
            "frontend", "database", "sql", "algorithm", "programming"
        ]
        science_keywords = [
            "biology", "chemistry", "physics", "math",
            "equation", "theorem", "experiment"
        ]
        business_keywords = [
            "marketing", "sales", "revenue", "startup",
            "business", "strategy", "management", "finance"
        ]
        religion_keywords = [
            "قرآن", "حديث", "إسلام", "صلاة", "الله",
            "quran", "hadith", "islam", "prayer"
        ]

        tags = []
        for kw in tech_keywords:
            if kw in text_lower:
                tags.append(kw)
        for kw in science_keywords:
            if kw in text_lower:
                tags.append(kw)
        for kw in business_keywords:
            if kw in text_lower:
                tags.append(kw)
        for kw in religion_keywords:
            if kw in text_lower:
                tags.append(kw)

        tags = list(set(tags))[:10]

        if any(k in text_lower for k in tech_keywords):
            category = Category.TECHNOLOGY
        elif any(k in text_lower for k in science_keywords):
            category = Category.SCIENCE
        elif any(k in text_lower for k in business_keywords):
            category = Category.BUSINESS
        elif any(k in text_lower for k in religion_keywords):
            category = Category.RELIGION
        else:
            category = Category.OTHER

        word_count = len(words)
        if word_count > 500:
            importance = 0.8
        elif word_count > 200:
            importance = 0.6
        elif word_count > 50:
            importance = 0.5
        else:
            importance = 0.3

        arabic_chars = sum(
            1 for c in text if '\u0600' <= c <= '\u06FF'
        )
        english_chars = sum(
            1 for c in text if c.isascii() and c.isalpha()
        )

        if arabic_chars > english_chars:
            language = Language.ARABIC
        elif english_chars > arabic_chars:
            language = Language.ENGLISH
        else:
            language = Language.MIXED

        sentences = text.replace('،', '.').split('.')
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        summary   = '. '.join(sentences[:3])
        if len(summary) > 300:
            summary = summary[:300] + "..."

        return tags, category, importance, language, summary

    def _calculate_hash(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()


# Singleton
ingest_pipeline = IngestPipeline()