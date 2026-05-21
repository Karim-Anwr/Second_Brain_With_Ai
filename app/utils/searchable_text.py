class SearchableTextBuilder:
    """
    بيبني نص غني للـ embedding بدل الـ chunk الخام.
    
    ليه مهم؟
    لو عمل embedding للـ chunk الخام بس:
    "RTX 4090 أداء ممتاز في الألعاب"
    
    الـ embedding هيكون ضعيف لأنه مش عارف السياق.
    
    بدل كده نبني:
    Title: لابتوب جيمينج
    Summary: مراجعة لابتوب بكارت RTX 4090
    Topics: gaming, laptops, GPU
    Keywords: RTX, 4090, لابتوب, جيمينج
    Chunk: RTX 4090 أداء ممتاز في الألعاب
    
    الـ embedding هيبقى أقوى بكتير!
    """

    def build(
        self,
        chunk: str,
        file_name: str,
        summary: str,
        topics: list[str],
        entities: list[str],
        keywords: list[str],
        tags: list[str],
        main_topic: str,
        chunk_summary: str = "",
        prev_context: str = "",
    ) -> str:
        """
        بيبني الـ searchable text الغني.
        """
        parts = []

        # Title
        if file_name:
            parts.append(f"Title: {file_name}")

        # Main Topic
        if main_topic:
            parts.append(f"Topic: {main_topic}")

        # Document Summary
        if summary:
            parts.append(f"Summary:\n{summary}")

        # Chunk Summary
        if chunk_summary:
            parts.append(f"Chunk Summary: {chunk_summary}")

        # Topics
        if topics:
            parts.append(f"Topics: {' | '.join(topics)}")

        # Entities
        if entities:
            parts.append(f"Entities: {' | '.join(entities)}")

        # Keywords
        if keywords:
            parts.append(f"Keywords: {' '.join(keywords)}")

        # Tags
        if tags:
            parts.append(f"Tags: {' '.join(tags)}")

        # Previous Context
        if prev_context:
            parts.append(f"Context: {prev_context[:200]}")

        # الـ chunk نفسه
        parts.append(f"Content:\n{chunk}")

        return "\n\n".join(parts)


# Singleton
searchable_text_builder = SearchableTextBuilder()