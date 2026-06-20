from app.services.vision_service import vision_service
from app.services.entity_enrichment_service import entity_enrichment


class MultimodalContextBuilder:
    """
    بيجمع كل المصادر في context واحد غني للـ embedding.
    
    المصادر:
    1. OCR Text         ← النص المكتوب في الصورة
    2. Vision Analysis  ← فهم بصري للصورة
    3. Entity Enrichment ← معلومات إضافية عن الـ entities
    4. LLM Analysis     ← تحليل المحتوى
    """

    def build_from_image(
        self,
        image_path: str,
        ocr_text: str,
        llm_analysis: dict,
    ) -> dict:
        """
        النقطة الرئيسية — بتاخد صورة وبترجع context كامل.
        """
        print("    Multimodal Context Builder...")

        # ════════════════════════════════
        # Step 1: Vision Analysis
        # ════════════════════════════════
        vision_result = vision_service.analyze_image(image_path)

        # ════════════════════════════════
        # Step 2: Entity Enrichment
        # ════════════════════════════════
        all_entities = list(set(
            vision_result.get("entities", []) +
            vision_result.get("people", []) +
            vision_result.get("brands", []) +
            llm_analysis.get("entities", [])
        ))

        enrichment = {}
        if all_entities:
            enrichment = entity_enrichment.enrich(
                entities=all_entities,
                content_type=vision_result.get("content_type", ""),
                visual_summary=vision_result.get("visual_summary", ""),
            )

        # ════════════════════════════════
        # Step 3: بناء الـ Knowledge Context
        # ════════════════════════════════
        knowledge_ctx = entity_enrichment.build_knowledge_context(
            vision_result=vision_result,
            enrichment=enrichment,
        )

        # ════════════════════════════════
        # Step 4: Unified Multimodal Context
        # ════════════════════════════════
        unified = self._build_unified_context(
            ocr_text=ocr_text,
            vision_result=vision_result,
            knowledge_ctx=knowledge_ctx,
            llm_analysis=llm_analysis,
        )

        # ════════════════════════════════
        # Step 5: Merge Metadata
        # ════════════════════════════════
        merged_tags = list(set(
            llm_analysis.get("tags", []) +
            vision_result.get("semantic_labels", []) +
            vision_result.get("topics", [])
        ))[:10]

        merged_entities = list(set(
            llm_analysis.get("entities", []) +
            all_entities
        ))[:8]

        merged_topics = list(set(
            llm_analysis.get("topics", []) +
            vision_result.get("topics", [])
        ))[:6]

        # لو OCR ضعيف خد summary من الـ vision
        # لو OCR فاضي، اعتمد على الـ Vision summary دايماً
# مش بس لما الجملة قصيرة — الجملة ممكن تكون طويلة وغير مفيدة
        ocr_is_empty = not ocr_text or len(ocr_text.strip()) < 10

        final_summary = llm_analysis.get("summary", "")
        if ocr_is_empty or not final_summary:
            vision_summary = vision_result.get("visual_summary", "")
            if vision_summary:
                final_summary = vision_summary
        print(f"   ✅ Multimodal context جاهز")

        return {
            # Context للـ embedding
            "unified_context":  unified,
            "knowledge_context": knowledge_ctx,

            # Vision fields
            "visual_summary":   vision_result.get("visual_summary", ""),
            "content_type":     vision_result.get("content_type", "other"),
            "detected_media":   vision_result.get("detected_media", []),
            "brands":           vision_result.get("brands", []),
            "products":         vision_result.get("products", []),
            "people":           vision_result.get("people", []),
            "franchise":        vision_result.get("franchise", ""),
            "confidence_score": vision_result.get("confidence_score", 0.0),
            "ocr_quality":      vision_result.get("ocr_quality", "none"),

            # Merged fields
            "tags":             merged_tags,
            "entities":         merged_entities,
            "topics":           merged_topics,
            "summary":          final_summary,

            # Original
            "vision_result":    vision_result,
            "enrichment":       enrichment,
        }

    def build_from_text(
        self,
        text: str,
        llm_analysis: dict,
    ) -> dict:
        """
        للـ text uploads — مفيش vision بس نبني context كويس.
        """
        return {
            "unified_context":  text,
            "knowledge_context": "",
            "visual_summary":   "",
            "content_type":     llm_analysis.get("content_type", "other"),
            "detected_media":   [],
            "brands":           [],
            "products":         [],
            "people":           [],
            "franchise":        "",
            "confidence_score": 1.0,
            "ocr_quality":      "good",
            "tags":             llm_analysis.get("tags", []),
            "entities":         llm_analysis.get("entities", []),
            "topics":           llm_analysis.get("topics", []),
            "summary":          llm_analysis.get("summary", ""),
            "vision_result":    {},
            "enrichment":       {},
        }

    def _build_unified_context(
    self,
    ocr_text: str,
    vision_result: dict,
    knowledge_ctx: str,
    llm_analysis: dict,
) -> str:
        parts = []

        ocr_is_empty = not ocr_text or len(ocr_text.strip()) < 10

        if not ocr_is_empty:
            parts.append(f"OCR TEXT:\n{ocr_text[:1000]}")

        visual = vision_result.get("visual_summary", "")
        if visual:
            parts.append(f"VISUAL UNDERSTANDING:\n{visual}")

        if knowledge_ctx:
            parts.append(f"KNOWLEDGE:\n{knowledge_ctx}")

        llm_summary = llm_analysis.get("summary", "")
        if llm_summary and not ocr_is_empty:
            parts.append(f"ANALYSIS:\n{llm_summary}")

        main_topic = llm_analysis.get("main_topic", "")
        if main_topic and main_topic != "اسم الملف":
            parts.append(f"MAIN TOPIC: {main_topic}")

        return "\n\n".join(parts)


# Singleton
_multimodal_builder = None

def get_multimodal_builder():
    global _multimodal_builder
    if _multimodal_builder is None:
        _multimodal_builder = MultimodalContextBuilder()
    return _multimodal_builder

multimodal_builder = get_multimodal_builder()