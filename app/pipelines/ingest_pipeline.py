import hashlib
from io import BytesIO
from pathlib import Path
import tempfile
from uuid import UUID
from fastapi import UploadFile
from sqlalchemy.orm import Session
from starlette.datastructures import Headers
from app.core.config import settings
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
from app.core.exceptions import InvalidRequestException, SecondBrainException, UnsafeURLError
from app.core.legacy_paths import legacy_global_resource_path
from app.services.graph_service import graph_service
from app.utils.file_handler import save_upload_file_owned


class IngestPipeline:

    def process_text_owned(self, db: Session, owner_user_id: UUID, text: str, title: str) -> MemoryResponse:
        """Create a new owner-scoped text memory without invoking the legacy global path."""
        return self._process_content_owned(
            db=db,
            owner_user_id=owner_user_id,
            text=text,
            file_name=title,
            file_type=FileType.TEXT.value,
            file_path="",
            file_id="",
            file_size=len(text.encode("utf-8")),
        )

    def process_owned(
        self,
        db: Session,
        owner_user_id: UUID,
        file_path: str,
        file_name: str,
        file_type: str,
        file_id: str = "",
        file_size: int = 0,
    ) -> MemoryResponse:
        """Create a new owner-scoped file-derived memory from an explicit owner path."""
        try:
            raw_text = ocr_service.extract_text(file_path=file_path, file_type=file_type)
        except Exception:
            raw_text = ""
        return self._process_content_owned(
            db=db,
            owner_user_id=owner_user_id,
            text=raw_text,
            file_name=file_name,
            file_type=file_type,
            file_path=file_path,
            file_id=file_id,
            file_size=file_size,
        )

    async def process_link_owned(self, db: Session, owner_user_id: UUID, url: str) -> MemoryResponse:
        """Ingest a link through explicit owner-scoped memory, file, and graph primitives only."""
        metadata, combined_text = self._build_link_content(url)
        thumbnail = await self._save_link_thumbnail_owned(
            db=db,
            owner_user_id=owner_user_id,
            thumbnail_url=metadata.get("thumbnail_url", ""),
        )
        platform = metadata.get("platform", "generic")
        file_name = metadata.get("title") or f"{platform} link"
        return self._process_content_owned(
            db=db,
            owner_user_id=owner_user_id,
            text=combined_text,
            file_name=file_name,
            file_type=FileType.LINK.value,
            file_path=thumbnail[1] if thumbnail else "",
            file_id=thumbnail[0] if thumbnail else "",
            file_size=len(combined_text),
        )

    def _build_link_content(self, url: str) -> tuple[dict, str]:
        metadata = link_service.extract_metadata(url)
        platform = metadata.get("platform", "generic")
        title = metadata.get("title", "")
        desc = metadata.get("description", "")
        author = metadata.get("author", "")

        text_parts = [f"Platform: {platform}"]
        if title:
            text_parts.append(f"Title: {title}")
        if author:
            text_parts.append(f"Author: {author}")
        if desc:
            text_parts.append(f"Description: {desc}")
        if platform in ("youtube", "tiktok"):
            try:
                audio_result = audio_service.process_video_audio(url)
                transcript = audio_result.get("text", "")
                if transcript:
                    text_parts.append(f"Transcript:\n{transcript}")
                    print(f"   ✅ Transcript اتضاف للمحتوى")
            except SecondBrainException as e:
                print(f"   ⚠️ مقدرناش نجيب الصوت: {e}")
        text_parts.append(f"URL: {url}")
        return metadata, "\n".join(text_parts)

    async def _save_link_thumbnail_owned(
        self, *, db: Session, owner_user_id: UUID, thumbnail_url: str
    ) -> tuple[str, str] | None:
        """Download a safe optional thumbnail and persist it only through the owned file primitive."""
        if not thumbnail_url:
            return None
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temporary_file:
            temporary_path = Path(temporary_file.name)
        temporary_path.unlink(missing_ok=True)
        try:
            try:
                downloaded = link_service.download_thumbnail(thumbnail_url, str(temporary_path))
            except UnsafeURLError:
                print("   ⚠️ تم تخطي الصورة المصغرة غير الآمنة")
                return None
            if not downloaded:
                return None
            thumbnail_bytes = temporary_path.read_bytes()
            content_type, extension = self._thumbnail_content_type(thumbnail_bytes)
            if content_type is None:
                return None
            upload = UploadFile(
                file=BytesIO(thumbnail_bytes),
                filename=f"link_thumbnail{extension}",
                headers=Headers({"content-type": content_type}),
            )
            try:
                thumbnail_id, thumbnail_path, _ = await save_upload_file_owned(db, owner_user_id, upload)
                return thumbnail_id, thumbnail_path
            finally:
                await upload.close()
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _thumbnail_content_type(content: bytes) -> tuple[str | None, str | None]:
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg", ".jpg"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png", ".png"
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
            return "image/webp", ".webp"
        return None, None

    def _process_content_owned(
        self,
        *,
        db: Session,
        owner_user_id: UUID,
        text: str,
        file_name: str,
        file_type: str,
        file_path: str,
        file_id: str,
        file_size: int,
    ) -> MemoryResponse:
        """Minimal explicit-owner path: build, register/project memory, then owner-scope graph linking."""
        cleaned_text = arabic_normalizer.clean_ocr_text(text) if text else ""
        chunks_obj = semantic_chunker.chunk(cleaned_text or file_name) or [Chunk(text=cleaned_text or file_name, index=0)]
        chunk_texts = [chunk.text for chunk in chunks_obj]
        memory = Memory(
            file_name=file_name,
            file_type=self._to_file_type(file_type),
            file_path=file_path,
            file_id=file_id,
            file_size=file_size,
            file_hash=self._calculate_hash(file_path) if file_path else "",
            raw_text=text,
            summary=(cleaned_text or file_name)[:500],
            chunks=chunk_texts,
            total_chunks=len(chunk_texts),
            recency_score=1.0,
        )
        searchable_texts = [
            searchable_text_builder.build(
                chunk=chunk,
                file_name=file_name,
                summary=memory.summary,
                topics=[],
                entities=[],
                keywords=[],
                tags=[],
                main_topic=file_name,
                prev_context="",
            )
            for chunk in chunk_texts
        ]
        embeddings = embedding_service.generate_batch(searchable_texts)
        memory.chunk_ids = [f"{memory.id}_chunk_{index}" for index in range(len(chunk_texts))]
        storage_service.save_memory_owned(
            db=db,
            owner_user_id=owner_user_id,
            memory=memory,
            embeddings=embeddings,
            searchable_texts=searchable_texts,
        )
        if embeddings:
            graph_service.auto_link_owned(
                db=db, owner_user_id=owner_user_id, memory_id=memory.id, embedding=embeddings[0]
            )
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

    @legacy_global_resource_path("ingestion")
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

    @legacy_global_resource_path("ingestion")
    def process_text(self, text: str, title: str) -> MemoryResponse:
        """Ingest direct user text through the existing shared content pipeline."""
        return self._process_content(
            text=text,
            file_name=title,
            file_type=FileType.TEXT.value,
            file_path="",
            file_size=len(text.encode("utf-8")),
            is_image=False,
        )

    @legacy_global_resource_path("ingestion")
    def process_link(self, url: str) -> MemoryResponse:
        """
        بياخد لينك ويحفظه كـ memory.
        لو فيديو من منصة مدعومة بالصوت (يوتيوب/تيك توك)،
        بيحاول يحول الصوت لنص كمان.
        """
        print(f"\n بدأ معالجة لينك: {url}")

        metadata, combined_text = self._build_link_content(url)
        platform = metadata.get("platform", "generic")
        title = metadata.get("title", "")
        thumb_url = metadata.get("thumbnail_url", "")

        thumbnail_path = None
        if thumb_url:
            thumb_id = uuid.uuid4().hex[:8]
            candidate_path = str(settings.upload_dir / f"link_{thumb_id}.jpg")
            try:
                if link_service.download_thumbnail(thumb_url, candidate_path):
                    thumbnail_path = candidate_path
            except UnsafeURLError:
                # A safe page remains ingestible when its optional image target is unsafe.
                print("   ⚠️ تم تخطي الصورة المصغرة غير الآمنة")

        file_name = title or f"{platform} link"

        return self._process_content(
            text=combined_text,
            file_name=file_name,
            file_type="link",
            file_path=thumbnail_path or "",
            file_size=len(combined_text),
            is_image=bool(thumbnail_path),
        )

    @legacy_global_resource_path("ingestion")
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
            file_type=self._to_file_type(file_type),
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

    @staticmethod
    def _to_file_type(file_type: str) -> FileType:
        try:
            return FileType(file_type)
        except ValueError as exc:
            raise InvalidRequestException("The supplied file type is unsupported.") from exc


# Singleton
ingest_pipeline = IngestPipeline()
