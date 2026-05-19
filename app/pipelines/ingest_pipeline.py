import hashlib
from app.services.ocr_service import ocr_service
from app.services.embedding_service import embedding_service
from app.services.storage_service import storage_service
from app.services.llm_service import llm_service
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

        # ════════════════════════════════
        # Step 1: OCR
        # ════════════════════════════════
        print("📖 Step 1: OCR...")
        raw_text = ocr_service.extract_text(
            file_path=file_path,
            file_type=file_type
        )
        print(f"   ✅ استخرج {len(raw_text.split())} كلمة")

        # ════════════════════════════════
        # Step 2: Groq يحلل المحتوى
        # ════════════════════════════════
        print("🤖 Step 2: Groq بيحلل المحتوى...")
        analysis = llm_service.analyze_content(
            text=raw_text,
            file_name=file_name
        )
        tags          = analysis.get("tags", [])
        importance    = float(analysis.get("importance_score", 0.5))
        summary       = analysis.get("summary", "")
        cleaned_text  = analysis.get("cleaned_text", raw_text)

        try:
            category = Category(analysis.get("category", "other"))
        except:
            category = Category.OTHER

        try:
            language = Language(analysis.get("language", "mixed"))
        except:
            language = Language.MIXED

        print(f"   ✅ Category: {category} | Tags: {tags[:3]}")

        # ════════════════════════════════
        # Step 3: Chunk
        # ════════════════════════════════
        print("✂️  Step 3: تقسيم لـ chunks...")
        chunks = chunk_text(
            text=cleaned_text,
            chunk_size=settings.max_chunk_size,
            overlap=settings.chunk_overlap
        )
        print(f"   ✅ {len(chunks)} chunk")

        # ════════════════════════════════
        # Step 4: Memory Object
        # ════════════════════════════════
        print("🧠 Step 4: بناء الـ Memory Object...")
        file_hash = self._calculate_hash(file_path)

        memory = Memory(
            file_name=file_name,
            file_type=FileType(file_type),
            file_path=file_path,
            file_size=file_size,
            file_hash=file_hash,
            raw_text=raw_text,
            summary=summary,
            tags=tags,
            category=category,
            importance_score=importance,
            language=language,
            chunks=chunks,
            total_chunks=len(chunks),
            recency_score=1.0,
        )

        # ════════════════════════════════
        # Step 5: Embedding
        # ════════════════════════════════
        print("🔢 Step 5: Embedding...")
        embeddings = embedding_service.generate_batch(chunks)
        print(f"   ✅ {len(embeddings)} vector")

        # ════════════════════════════════
        # Step 6: Save
        # ════════════════════════════════
        print("💾 Step 6: حفظ في ChromaDB...")
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

        # ════════════════════════════════
        # Step 1: Groq يحلل المحتوى
        # ════════════════════════════════
        print("🤖 Step 1: Groq بيحلل المحتوى...")
        analysis     = llm_service.analyze_content(
            text=text,
            file_name=title
        )
        tags          = analysis.get("tags", [])
        importance    = float(analysis.get("importance_score", 0.5))
        summary       = analysis.get("summary", "")
        cleaned_text  = analysis.get("cleaned_text", text)

        try:
            category = Category(analysis.get("category", "other"))
        except:
            category = Category.OTHER

        try:
            language = Language(analysis.get("language", "mixed"))
        except:
            language = Language.MIXED

        print(f"   ✅ Category: {category} | Tags: {tags[:3]}")

        # ════════════════════════════════
        # Step 2: Chunk
        # ════════════════════════════════
        print("✂️  Step 2: تقسيم لـ chunks...")
        chunks = chunk_text(
            text=cleaned_text,
            chunk_size=settings.max_chunk_size,
            overlap=settings.chunk_overlap
        )
        print(f"   ✅ {len(chunks)} chunk")

        # ════════════════════════════════
        # Step 3: Memory Object
        # ════════════════════════════════
        memory = Memory(
            file_name=title,
            file_type=FileType.TEXT,
            file_path="",
            file_size=len(text),
            file_hash="",
            raw_text=text,
            summary=summary,
            tags=tags,
            category=category,
            importance_score=importance,
            language=language,
            chunks=chunks,
            total_chunks=len(chunks),
            recency_score=1.0,
        )

        # ════════════════════════════════
        # Step 4: Embedding
        # ════════════════════════════════
        print("🔢 Step 3: Embedding...")
        embeddings = embedding_service.generate_batch(chunks)
        print(f"   ✅ {len(embeddings)} vector")

        # ════════════════════════════════
        # Step 5: Save
        # ════════════════════════════════
        print("💾 Step 4: حفظ في ChromaDB...")
        memory.chunk_ids = [
            f"{memory.id}_chunk_{i}"
            for i in range(len(chunks))
        ]
        storage_service.save_memory(memory=memory, embeddings=embeddings)

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

    def _calculate_hash(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()


# Singleton
ingest_pipeline = IngestPipeline()