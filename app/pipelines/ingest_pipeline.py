import hashlib
from app.services.ocr_service import ocr_service
from app.services.embedding_service import embedding_service
from app.services.storage_service import storage_service
from app.services.llm_service import llm_service

from app.models.memory import (
    Memory,
    FileType,
    Category,
    Language,
    MemoryResponse,
)

from app.utils.arabic_normalizer import arabic_normalizer
from app.utils.semantic_chunker import semantic_chunker, Chunk
from app.utils.searchable_text import searchable_text_builder

from app.core.exceptions import StorageException


class IngestPipeline:

    # ============================================================
    # OCR ENTRY
    # ============================================================

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

        return self._process_content(
            text=raw_text,
            file_name=file_name,
            file_type=file_type,
            file_path=file_path,
            file_size=file_size,
        )

    # ============================================================
    # TEXT ENTRY
    # ============================================================

    def process_text(self, text: str, title: str) -> MemoryResponse:

        print(f"\n🚀 بدأ معالجة نص: {title}")

        return self._process_content(
            text=text,
            file_name=title,
            file_type="text",
            file_path="",
            file_size=len(text),
        )

    # ============================================================
    # CORE PIPELINE
    # ============================================================

    def _process_content(
        self,
        text: str,
        file_name: str,
        file_type: str,
        file_path: str,
        file_size: int,
    ) -> MemoryResponse:

        # -----------------------------
        # Step 1: Normalize Text
        # -----------------------------
        print("🔤 Step 1: Normalization...")

        cleaned_text = arabic_normalizer.clean_ocr_text(text)

        if not cleaned_text or len(cleaned_text) < 20:
            cleaned_text = text

        print("   ✅ النص اتنظف")

        # -----------------------------
        # Step 2: LLM Analysis
        # -----------------------------
        print("🤖 Step 2: LLM Analysis...")

        analysis = llm_service.analyze_content(
            text=cleaned_text,
            file_name=file_name
        )

        tags        = analysis.get("tags", [])
        keywords    = analysis.get("keywords", [])
        entities    = analysis.get("entities", [])
        topics      = analysis.get("topics", [])
        summary     = analysis.get("summary", "")
        main_topic  = analysis.get("main_topic", file_name)
        importance  = float(analysis.get("importance_score", 0.5))
        content_type = analysis.get("content_type", "other")

        groq_cleaned = analysis.get("cleaned_text", "")
        if groq_cleaned and len(groq_cleaned) > 50:
            cleaned_text = groq_cleaned

        try:
            category = Category(analysis.get("category", "other"))
        except:
            category = Category.OTHER

        try:
            language = Language(analysis.get("language", "mixed"))
        except:
            language = Language.MIXED

        print(f"   ✅ Topic: {main_topic}")

        # -----------------------------
        # Step 3: Semantic Chunking
        # -----------------------------
        print("✂️ Step 3: Chunking...")

        chunks_obj = semantic_chunker.chunk(cleaned_text)

        if not chunks_obj:
            chunks_obj = [Chunk(text=cleaned_text, index=0, prev_context="")]

        chunk_texts = [c.text for c in chunks_obj]

        print(f"   ✅ {len(chunk_texts)} chunk")

        # -----------------------------
        # Step 4: Build Searchable Text
        # -----------------------------
        print("📝 Step 4: Searchable Text...")

        searchable_texts = []

        for chunk_obj in chunks_obj:
            st = searchable_text_builder.build(
                chunk=chunk_obj.text,
                file_name=file_name,
                summary=summary,
                topics=topics,
                entities=entities,
                keywords=keywords,
                tags=tags,
                main_topic=main_topic,
                prev_context=chunk_obj.prev_context,
            )
            searchable_texts.append(st)

        print(f"   ✅ {len(searchable_texts)} searchable texts")

        # -----------------------------
        # Step 5: Memory Object
        # -----------------------------
        print("🧠 Step 5: Memory Build...")

        file_hash = ""
        if file_path:
            try:
                file_hash = self._calculate_hash(file_path)
            except:
                pass

        try:
            ft = FileType(file_type)
        except:
            ft = FileType.TEXT

        memory = Memory(
            file_name=file_name,
            file_type=ft,
            file_path=file_path,
            file_size=file_size,
            file_hash=file_hash,
            raw_text=text,
            summary=summary,
            tags=tags,
            category=category,
            importance_score=importance,
            language=language,
            chunks=chunk_texts,
            total_chunks=len(chunk_texts),
            recency_score=1.0,
        )

        # attach AI metadata (safe)
        memory.keywords = keywords
        memory.entities = entities
        memory.topics = topics
        memory.main_topic = main_topic
        memory.content_type = content_type

        # -----------------------------
        # Step 6: Embedding
        # -----------------------------
        print("🔢 Step 6: Embedding...")

        embeddings = embedding_service.generate_batch(
            searchable_texts,
            show_progress=True
        )

        print(f"   ✅ {len(embeddings)} vectors")

        # -----------------------------
        # Step 7: Save to Storage
        # -----------------------------
        print("💾 Step 7: Saving...")

        memory.chunk_ids = [
            f"{memory.id}_chunk_{i}"
            for i in range(len(chunk_texts))
        ]

        storage_service.save_memory(
            memory=memory,
            embeddings=embeddings,
            searchable_texts=searchable_texts,
        )

        print(f"   ✅ Saved successfully")

        # -----------------------------
        # Final Response
        # -----------------------------
        return MemoryResponse(
             memory_id=memory.id,
            file_name=memory.file_name,
            file_type=memory.file_type,
            summary=memory.summary,
            tags=memory.tags,
            category=memory.category,
            importance=memory.importance_score,
            total_chunks=memory.total_chunks,
            status="success",

    # 🔥 add these
            keywords=getattr(memory, "keywords", []),
            entities=getattr(memory, "entities", []),
            topics=getattr(memory, "topics", []),
            language=memory.language,
            content_type=getattr(memory, "content_type", "")
)

    # ============================================================
    # HASH
    # ============================================================

    def _calculate_hash(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()


# ============================================================
# Singleton
# ============================================================

ingest_pipeline = IngestPipeline()