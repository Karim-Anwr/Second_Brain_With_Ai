import hashlib
from app.services.ocr_service import ocr_service
from app.services.embedding_service import embedding_service
from app.services.storage_service import storage_service
from app.services.llm_service import llm_service
from app.services.multimodal_context_builder import multimodal_builder
from app.models.memory import Memory, FileType, Category, Language, MemoryResponse
from app.utils.arabic_normalizer import arabic_normalizer
from app.utils.semantic_chunker import semantic_chunker, Chunk
from app.utils.searchable_text import searchable_text_builder
import uuid
from app.services.link_service import link_service
from app.services.audio_service import audio_service
from app.core.exceptions import SecondBrainException
from app.services.graph_service import graph_service


class IngestPipeline:

    def process(self, file_path, file_name, file_type, file_size=0):

        print(f"\n بدأ معالجة: {file_name}")

        print(" Step 1: OCR...")
        try:
            raw_text = ocr_service.extract_text(file_path=file_path, file_type=file_type)
        except Exception as e:
            print(f" OCR فشل: {e}")
            raw_text = ""

        return self._process_content(
            text=raw_text,
            file_name=file_name,
            file_type=file_type,
            file_path=file_path,
            file_size=file_size,
            is_image=file_type == "image",
        )
    def process_link(self, url: str) -> MemoryResponse:
        """
        بياخد لينك ويحفظه كـ memory.
        لو فيديو من منصة مدعومة بالصوت (يوتيوب/تيك توك)،
        بيحاول يحول الصوت لنص كمان.
        """
        print(f"\n بدأ معالجة لينك: {url}")

        metadata  = link_service.extract_metadata(url)
        platform  = metadata.get("platform", "generic")
        title     = metadata.get("title", "")
        desc      = metadata.get("description", "")
        author    = metadata.get("author", "")
        thumb_url = metadata.get("thumbnail_url", "")

        text_parts = [f"Platform: {platform}"]
        if title:
            text_parts.append(f"Title: {title}")
        if author:
            text_parts.append(f"Author: {author}")
        if desc:
            text_parts.append(f"Description: {desc}")

        # ── محاولة استخراج الصوت لو المنصة بتدعم (يوتيوب/تيك توك) ──
        if platform in ("youtube", "tiktok"):
            try:
                audio_result = audio_service.process_video_audio(url)
                transcript = audio_result.get("text", "")
                if transcript:
                    text_parts.append(f"Transcript:\n{transcript}")
                    print(f"   ✅ Transcript اتضاف للمحتوى")
            except SecondBrainException as e:
                print(f"   ⚠️ مقدرناش نجيب الصوت: {e}")
                # نكمل عادي بالعنوان والوصف بس

        text_parts.append(f"URL: {url}")
        combined_text = "\n".join(text_parts)

        thumbnail_path = None
        if thumb_url:
            thumb_id = uuid.uuid4().hex[:8]
            candidate_path = f"storage/uploads/link_{thumb_id}.jpg"
            if link_service.download_thumbnail(thumb_url, candidate_path):
                thumbnail_path = candidate_path

        file_name = title or f"{platform} link"

        return self._process_content(
            text=combined_text,
            file_name=file_name,
            file_type="link",
            file_path=thumbnail_path or "",
            file_size=len(combined_text),
            is_image=bool(thumbnail_path),
        )

    def _process_content(
        self,
        text,
        file_name,
        file_type,
        file_path,
        file_size,
        is_image=False,
    ):

        # =========================
        # Normalization
        # =========================
        print(" Step 2: Normalization...")
        cleaned_text = arabic_normalizer.clean_ocr_text(text) if text else ""

        # =========================
        # LLM Analysis (FIXED INPUT)
        # =========================
        print(" Step 3: LLM Analysis...")

        analysis_input = cleaned_text.strip()

        if is_image and not analysis_input:
            analysis_input = ""   # مهم: سيبه فاضي للـ vision
        elif not analysis_input:
            analysis_input = file_name

        llm_analysis = llm_service.analyze_content(
            text=analysis_input,
            file_name=file_name,
        )

        # =========================
        # Multimodal
        # =========================
        print(" Step 4: Multimodal...")

        if is_image and file_path:
            multimodal = multimodal_builder.build_from_image(
                image_path=file_path,
                ocr_text=cleaned_text,
                llm_analysis=llm_analysis,
            )
        else:
            multimodal = multimodal_builder.build_from_text(
                text=cleaned_text,
                llm_analysis=llm_analysis,
            )

        vision = multimodal.get("vision_result", {})

        # =========================
        # OVERRIDE (IMPORTANT FIX)
        # =========================

        summary = multimodal.get("summary", "")

        bad_summaries = ["اسم ملف", "ملف صورة", "لا يوجد", "النص يحتوي على اسم ملف"]

        if (
            not summary
            or len(summary) < 20
            or any(x in summary for x in bad_summaries)
        ):
            summary = vision.get("visual_summary", "")

        main_topic = llm_analysis.get("main_topic", file_name)

        if is_image:
            if vision.get("detected_media"):
                main_topic = vision["detected_media"][0]
            elif vision.get("content_type"):
                main_topic = vision["content_type"]

        # =========================
        # Metadata merge
        # =========================

        tags = multimodal.get("tags", [])
        entities = multimodal.get("entities", [])
        topics = multimodal.get("topics", [])

        visual_summary = multimodal.get("visual_summary", "")
        detected_media = multimodal.get("detected_media", [])
        brands = multimodal.get("brands", [])
        products = multimodal.get("products", [])
        people = multimodal.get("people", [])

        # =========================
        # Chunking
        # =========================
        print(" Step 5: Chunking...")

        chunks_obj = semantic_chunker.chunk(multimodal.get("unified_context", cleaned_text))

        if not chunks_obj:
            chunks_obj = [Chunk(text=cleaned_text or file_name, index=0)]

        chunk_texts = [c.text for c in chunks_obj]

        # =========================
        # Searchable text
        # =========================
        print(" Step 6: Searchable Text...")

        searchable_texts = []

        for i, chunk in enumerate(chunks_obj):

            enhanced = chunk.text

            if visual_summary and is_image:
                enhanced += f"\n\nVISUAL: {visual_summary}"

            st = searchable_text_builder.build(
                chunk=enhanced,
                file_name=file_name,
                summary=summary,
                topics=topics + detected_media,
                entities=entities + people + brands,
                keywords=products,
                tags=tags,
                main_topic=main_topic,
                prev_context=getattr(chunk, "prev_context", ""),
            )

            searchable_texts.append(st)

        # =========================
        # Memory object
        # =========================
        print(" Step 7: Memory Build...")

        try:
            category = Category(llm_analysis.get("category", "other"))
        except:
            category = Category.OTHER

        try:
            language = Language(llm_analysis.get("language", "mixed"))
        except:
            language = Language.MIXED

        memory = Memory(
            file_name=file_name,
            file_type=FileType(file_type) if file_type in ["image", "text"] else FileType.TEXT,
            file_path=file_path,
            file_size=file_size,
            file_hash=self._calculate_hash(file_path) if file_path else "",

            raw_text=text,
            summary=summary,

            tags=tags,
            keywords=llm_analysis.get("keywords", []),
            entities=entities,
            topics=topics,

            main_topic=main_topic,
            content_type=multimodal.get("content_type", "other"),
            category=category,
            importance_score=float(llm_analysis.get("importance_score", 0.5)),
            language=language,

            chunks=chunk_texts,
            total_chunks=len(chunk_texts),
            recency_score=1.0,

            visual_summary=visual_summary,
            detected_media=detected_media,
            brands=brands,
            products=products,
            people=people,
        )



        # =========================
        # Embedding + Save
        # =========================
        print(" Step 8: Embedding...")

        embeddings = embedding_service.generate_batch(searchable_texts)

        memory.chunk_ids = [
            f"{memory.id}_chunk_{i}"
            for i in range(len(chunk_texts))
        ]

        print(" Step 9: Saving...")

        storage_service.save_memory(
            memory=memory,
            embeddings=embeddings,
            searchable_texts=searchable_texts,
        )
        print("  Step 10: ربط تلقائي بذكريات مشابهة...")
        try:
            # بنستخدم أول embedding كممثل للذكرى كلها
            linked_count = graph_service.auto_link(
                memory_id=memory.id,
                embedding=embeddings[0],
            )
            print(f"   ✅ اترتبط بـ {linked_count} ذكرى مشابهة")
        except Exception as e:
            print(f"   ⚠️ Auto-link فشل: {e}")
            

        print(f"\n Memory ID: {memory.id}")

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
        )

    def _calculate_hash(self, file_path):
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()


# Singleton
ingest_pipeline = IngestPipeline()