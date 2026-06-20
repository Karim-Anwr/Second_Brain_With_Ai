import json
from app.services.llm_service import llm_service


class EntityEnrichmentService:
    """
    بيغني الـ entities المكتشفة بمعلومات إضافية.
    
    مثال:
    Entity: "Avengers"
    Enriched: {
        type: "movie",
        franchise: "Marvel",
        genre: ["action", "superhero"],
        related: ["Iron Man", "Thor", "MCU"]
    }
    """

    def enrich(
        self,
        entities: list[str],
        content_type: str,
        visual_summary: str,
    ) -> dict:
        """
        بيغني الـ entities بمعلومات إضافية من الـ LLM.
        """
        if not entities:
            return {}

        prompt = f"""أنت نظام إثراء معلومات ذكي.

نوع المحتوى: {content_type}
وصف الصورة: {visual_summary}
الـ entities المكتشفة: {', '.join(entities)}

أضف معلومات مفيدة عن الـ entities دي وارجع JSON فقط:
{{
    "enriched_entities": [
        {{
            "name": "اسم الـ entity",
            "type": "movie|anime|game|brand|celebrity|character|other",
            "description": "وصف مختصر",
            "related_terms": ["مصطلح1", "مصطلح2"],
            "genre": ["genre1"],
            "franchise": "اسم الـ franchise لو موجود"
        }}
    ],
    "knowledge_tags": ["tag1", "tag2", "tag3"],
    "search_suggestions": ["بحث1", "بحث2"]
}}

ركز على المعلومات اللي هتساعد في البحث لاحقاً."""

        try:
            response = llm_service._call(prompt, fast=True)
            return llm_service._parse_json(response)
        except Exception as e:
            print(f"⚠️ Entity enrichment فشل: {e}")
            return {
                "enriched_entities":  [],
                "knowledge_tags":     entities,
                "search_suggestions": entities,
            }

    def build_knowledge_context(
        self,
        vision_result: dict,
        enrichment: dict,
    ) -> str:
        """
        بيبني نص غني من الـ vision result والـ enrichment.
        """
        parts = []

        # Content Type
        ct = vision_result.get("content_type", "")
        if ct:
            parts.append(f"Content Type: {ct}")

        # Title
        title = vision_result.get("title", "")
        if title:
            parts.append(f"Title: {title}")

        # Franchise
        franchise = vision_result.get("franchise", "")
        if franchise:
            parts.append(f"Franchise: {franchise}")

        # Visual Summary
        summary = vision_result.get("visual_summary", "")
        if summary:
            parts.append(f"Visual Description: {summary}")

        # Entities
        entities = vision_result.get("entities", [])
        if entities:
            parts.append(f"Characters/Entities: {', '.join(entities)}")

        # People
        people = vision_result.get("people", [])
        if people:
            parts.append(f"People: {', '.join(people)}")

        # Brands
        brands = vision_result.get("brands", [])
        if brands:
            parts.append(f"Brands: {', '.join(brands)}")

        # Products
        products = vision_result.get("products", [])
        if products:
            parts.append(f"Products: {', '.join(products)}")

        # Topics
        topics = vision_result.get("topics", [])
        if topics:
            parts.append(f"Topics: {', '.join(topics)}")

        # Semantic Labels
        labels = vision_result.get("semantic_labels", [])
        if labels:
            parts.append(f"Semantic Labels: {', '.join(labels)}")

        # Enriched Knowledge
        knowledge_tags = enrichment.get("knowledge_tags", [])
        if knowledge_tags:
            parts.append(f"Knowledge Tags: {', '.join(knowledge_tags)}")

        # Search Suggestions
        suggestions = enrichment.get("search_suggestions", [])
        if suggestions:
            parts.append(f"Related Searches: {', '.join(suggestions)}")

        return "\n".join(parts)


# Singleton
_entity_enrichment = None

def get_entity_enrichment():
    global _entity_enrichment
    if _entity_enrichment is None:
        _entity_enrichment = EntityEnrichmentService()
    return _entity_enrichment

entity_enrichment = get_entity_enrichment()