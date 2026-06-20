import json
from pathlib import Path
from datetime import datetime


class GraphService:
    """
    مسؤول عن العلاقات بين الذكريات (Memory Graph).
    
    بيخزن edges بسيطة: from → to + نوع العلاقة + قوتها.
    زي الـ sessions، بنخزنها كـ JSON خفيف بدل ما نضيف
    graph database كاملة — مناسب لحجم البيانات دلوقتي.
    """

    def __init__(self):
        self.graph_dir  = Path("storage/graph")
        self.graph_dir.mkdir(parents=True, exist_ok=True)
        self.edges_path = self.graph_dir / "edges.json"
        if not self.edges_path.exists():
            self._save_edges([])
        print("✅ Graph Service جاهز!")

    # ============================================================
    # تخزين أساسي
    # ============================================================

    def _load_edges(self) -> list[dict]:
        with open(self.edges_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_edges(self, edges: list[dict]):
        with open(self.edges_path, "w", encoding="utf-8") as f:
            json.dump(edges, f, ensure_ascii=False, indent=2)

    # ============================================================
    # إضافة علاقة
    # ============================================================

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        relation_type: str = "semantic",
        score: float = 0.5,
    ) -> bool:
        """
        بيضيف علاقة بين ذكرتين.
        relation_type: semantic (تشابه تلقائي) | manual (ربط يدوي)
        """
        if from_id == to_id:
            return False

        edges = self._load_edges()

        # امنع التكرار — لو العلاقة موجودة، حدّث الـ score بس
        for edge in edges:
            same_pair = (
                (edge["from"] == from_id and edge["to"] == to_id) or
                (edge["from"] == to_id and edge["to"] == from_id)
            )
            if same_pair:
                edge["score"] = max(edge["score"], score)
                self._save_edges(edges)
                return True

        edges.append({
            "from":          from_id,
            "to":            to_id,
            "relation_type": relation_type,
            "score":         round(score, 4),
            "created_at":    datetime.now().isoformat(),
        })
        self._save_edges(edges)
        return True

    def remove_edge(self, from_id: str, to_id: str) -> bool:
        edges  = self._load_edges()
        before = len(edges)
        edges  = [
            e for e in edges
            if not (
                (e["from"] == from_id and e["to"] == to_id) or
                (e["from"] == to_id and e["to"] == from_id)
            )
        ]
        self._save_edges(edges)
        return len(edges) < before

    # ============================================================
    # جلب العلاقات
    # ============================================================

    def get_related(
        self,
        memory_id: str,
        depth: int = 1,
        min_score: float = 0.0,
    ) -> list[dict]:
        """
        بيرجع الذكريات المرتبطة بذكرى معينة.
        depth=1 → جيران مباشرين بس
        depth=2 → جيران الجيران كمان (هينفع في الـ Phase الجاية)
        """
        edges   = self._load_edges()
        visited = {memory_id}
        frontier = {memory_id}
        results = []

        for _ in range(depth):
            next_frontier = set()
            for edge in edges:
                if edge["score"] < min_score:
                    continue

                neighbor = None
                if edge["from"] in frontier and edge["to"] not in visited:
                    neighbor = edge["to"]
                elif edge["to"] in frontier and edge["from"] not in visited:
                    neighbor = edge["from"]

                if neighbor:
                    results.append({
                        "memory_id":     neighbor,
                        "relation_type": edge["relation_type"],
                        "score":         edge["score"],
                    })
                    visited.add(neighbor)
                    next_frontier.add(neighbor)

            frontier = next_frontier
            if not frontier:
                break

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def auto_link(
        self,
        memory_id: str,
        embedding: list[float],
        top_k: int = 3,
        similarity_threshold: float = 0.6,
    ) -> int:
        """
        بيدور تلقائياً على ذكريات شبيهة وقت الـ upload
        ويربطهم. بيتنادى من ingest_pipeline.
        """
        from app.services.storage_service import storage_service

        try:
            raw_results = storage_service.search_raw_chunks(
                query_embedding=embedding,
                top_k=top_k + 5,  # هنفلتر نفس الذكرى وهنخد top_k بعدين
            )
        except Exception:
            return 0

        linked = 0
        seen_ids = {memory_id}

        for chunk in raw_results:
            other_id = chunk.get("metadata", {}).get("memory_id", "")
            score    = chunk.get("semantic_score", 0)

            if other_id in seen_ids:
                continue
            seen_ids.add(other_id)

            if score >= similarity_threshold:
                self.add_edge(
                    from_id=memory_id,
                    to_id=other_id,
                    relation_type="semantic",
                    score=score,
                )
                linked += 1

            if linked >= top_k:
                break

        return linked


# Singleton
_graph_service = None

def get_graph_service():
    global _graph_service
    if _graph_service is None:
        _graph_service = GraphService()
    return _graph_service

graph_service = get_graph_service()