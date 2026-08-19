import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from app.core.config import settings


class GraphService:
    """Lightweight local graph persistence with atomic JSON updates."""

    def __init__(self):
        self.graph_dir = Path(settings.graph_dir)
        self.graph_dir.mkdir(parents=True, exist_ok=True)
        self.edges_path = self.graph_dir / "edges.json"
        self._lock = threading.RLock()
        if not self.edges_path.exists():
            self._save_edges([])
        print("✅ Graph Service جاهز!")

    def _load_edges(self) -> list[dict]:
        with self._lock:
            try:
                with open(self.edges_path, "r", encoding="utf-8") as source:
                    data = json.load(source)
                return data if isinstance(data, list) else []
            except (OSError, json.JSONDecodeError):
                return []

    def _save_edges(self, edges: list[dict]) -> None:
        temporary_name: str | None = None
        with self._lock:
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=self.graph_dir, prefix=".edges.", suffix=".tmp", delete=False
                ) as temp_file:
                    temporary_name = temp_file.name
                    json.dump(edges, temp_file, ensure_ascii=False, indent=2)
                    temp_file.flush()
                    os.fsync(temp_file.fileno())
                os.replace(temporary_name, self.edges_path)
            finally:
                if temporary_name and Path(temporary_name).exists():
                    Path(temporary_name).unlink(missing_ok=True)

    def add_edge(self, from_id: str, to_id: str, relation_type: str = "semantic", score: float = 0.5) -> bool:
        if from_id == to_id:
            return False
        with self._lock:
            edges = self._load_edges()
            for edge in edges:
                same_pair = (edge["from"] == from_id and edge["to"] == to_id) or (
                    edge["from"] == to_id and edge["to"] == from_id
                )
                if same_pair:
                    edge["score"] = max(edge["score"], score)
                    self._save_edges(edges)
                    return True
            edges.append(
                {
                    "from": from_id,
                    "to": to_id,
                    "relation_type": relation_type,
                    "score": round(score, 4),
                    "created_at": datetime.now().isoformat(),
                }
            )
            self._save_edges(edges)
            return True

    def remove_edge(self, from_id: str, to_id: str) -> bool:
        with self._lock:
            edges = self._load_edges()
            before = len(edges)
            edges = [
                edge
                for edge in edges
                if not ((edge["from"] == from_id and edge["to"] == to_id) or (edge["from"] == to_id and edge["to"] == from_id))
            ]
            self._save_edges(edges)
            return len(edges) < before

    def get_related(self, memory_id: str, depth: int = 1, min_score: float = 0.0) -> list[dict]:
        edges = self._load_edges()
        visited = {memory_id}
        frontier = {memory_id}
        results = []
        for _ in range(depth):
            next_frontier = set()
            for edge in edges:
                if edge.get("score", 0) < min_score:
                    continue
                neighbor = None
                if edge.get("from") in frontier and edge.get("to") not in visited:
                    neighbor = edge["to"]
                elif edge.get("to") in frontier and edge.get("from") not in visited:
                    neighbor = edge["from"]
                if neighbor:
                    results.append({"memory_id": neighbor, "relation_type": edge.get("relation_type", "semantic"), "score": edge.get("score", 0.0)})
                    visited.add(neighbor)
                    next_frontier.add(neighbor)
            frontier = next_frontier
            if not frontier:
                break
        return sorted(results, key=lambda item: item["score"], reverse=True)

    def auto_link(self, memory_id: str, embedding: list[float], top_k: int = 3, similarity_threshold: float = 0.6) -> int:
        from app.services.storage_service import storage_service

        try:
            raw_results = storage_service.search_raw_chunks(query_embedding=embedding, top_k=top_k + 5)
        except Exception:
            return 0

        linked = 0
        seen_ids = {memory_id}
        for chunk in raw_results:
            other_id = chunk.get("metadata", {}).get("memory_id", "")
            score = chunk.get("semantic_score", 0)
            if other_id in seen_ids:
                continue
            seen_ids.add(other_id)
            if score >= similarity_threshold:
                self.add_edge(memory_id, other_id, "semantic", score)
                linked += 1
            if linked >= top_k:
                break
        return linked


_graph_service: GraphService | None = None


def get_graph_service() -> GraphService:
    global _graph_service
    if _graph_service is None:
        _graph_service = GraphService()
    return _graph_service


graph_service = get_graph_service()
