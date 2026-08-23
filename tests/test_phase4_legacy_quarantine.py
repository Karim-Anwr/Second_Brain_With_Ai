"""Static capability-boundary checks for Phase 4 legacy global-path quarantine."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import UUID

import pytest

from app.api.routes import chat as chat_routes
from app.api.routes import search as search_routes
from app.api.routes import upload as upload_routes
from app.core.config import settings
from app.core.legacy_paths import legacy_global_resource_path
from app.pipelines.context_builder import ContextBuilder
from app.pipelines.conversation_pipeline import ConversationPipeline
from app.pipelines.ingest_pipeline import IngestPipeline
from app.pipelines.search_pipeline import SearchPipeline
from app.services.conversation_service import ConversationService
from app.services.graph_service import GraphService
from app.services.session_service import SessionService
from app.services.storage_service import StorageService
from app.utils import file_handler


GLOBAL_RESOURCE_METHODS = {
    "add_edge",
    "add_message",
    "auto_link",
    "chat",
    "create_session",
    "delete_session",
    "get_episodic_memory",
    "get_extracted_memories",
    "get_total_memories",
    "get_long_term_memory",
    "get_recent_messages",
    "get_related",
    "get_session",
    "get_short_term_memory",
    "increment_access_count",
    "list_sessions",
    "memory_exists",
    "process",
    "process_and_extract",
    "process_link",
    "process_text",
    "remove_edge",
    "retrieve",
    "remove_upload_file",
    "save_upload_file",
    "save_as_memory",
    "save_conversation_memory",
    "save_extracted_memory",
    "save_memory",
    "search",
    "search_by_filter",
    "search_raw_chunks",
    "set_favorite",
    "summarize_session",
    "update_session_summary",
}


LEGACY_MARKERS = (
    (StorageService, "save_memory", "memory"),
    (StorageService, "search", "memory"),
    (StorageService, "search_raw_chunks", "memory"),
    (StorageService, "increment_access_count", "memory"),
    (StorageService, "get_total_memories", "memory"),
    (StorageService, "set_favorite", "memory"),
    (StorageService, "memory_exists", "memory"),
    (SessionService, "create_session", "session"),
    (SessionService, "get_session", "session"),
    (SessionService, "list_sessions", "session"),
    (SessionService, "delete_session", "session"),
    (SessionService, "add_message", "session"),
    (SessionService, "get_recent_messages", "session"),
    (SessionService, "update_session_summary", "session"),
    (SessionService, "save_extracted_memory", "session"),
    (SessionService, "get_extracted_memories", "session"),
    (GraphService, "add_edge", "graph"),
    (GraphService, "remove_edge", "graph"),
    (GraphService, "get_related", "graph"),
    (GraphService, "auto_link", "graph"),
    (ConversationService, "get_short_term_memory", "conversation"),
    (ConversationService, "get_long_term_memory", "conversation"),
    (ConversationService, "save_as_memory", "conversation"),
    (ConversationService, "save_conversation_memory", "conversation"),
    (ConversationService, "process_and_extract", "conversation"),
    (ConversationService, "get_episodic_memory", "conversation"),
    (ConversationService, "summarize_session", "conversation"),
    (IngestPipeline, "process", "ingestion"),
    (IngestPipeline, "process_text", "ingestion"),
    (IngestPipeline, "process_link", "ingestion"),
    (IngestPipeline, "_process_content", "ingestion"),
    (SearchPipeline, "retrieve", "search"),
    (SearchPipeline, "search", "search"),
    (SearchPipeline, "search_by_filter", "search"),
    (ConversationPipeline, "chat", "conversation"),
    (ContextBuilder, "build", "conversation"),
)


def _is_legacy_marker(decorator: ast.expr) -> bool:
    return isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name) and decorator.func.id == "legacy_global_resource_path"


class _GlobalCallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.function_stack: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self.unmarked_calls: list[tuple[str, int, str]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_stack.append(node)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.function_stack.append(node)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        is_context_builder_call = (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "build"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "context_builder"
        )
        if isinstance(node.func, ast.Attribute) and (node.func.attr in GLOBAL_RESOURCE_METHODS or is_context_builder_call):
            enclosing = self.function_stack[-1] if self.function_stack else None
            if enclosing is None or not any(_is_legacy_marker(item) for item in enclosing.decorator_list):
                function_name = enclosing.name if enclosing is not None else "<module>"
                self.unmarked_calls.append((function_name, node.lineno, node.func.attr))
        self.generic_visit(node)


def test_every_retained_global_resource_api_is_explicitly_classified() -> None:
    for owner, method_name, category in LEGACY_MARKERS:
        assert getattr(owner, method_name).__legacy_global_resource_path__ == category

    assert file_handler.save_upload_file.__legacy_global_resource_path__ == "file"
    assert file_handler.remove_upload_file.__legacy_global_resource_path__ == "file"


def test_no_production_call_reaches_global_resource_api_outside_explicit_legacy_path() -> None:
    app_root = Path(__file__).resolve().parents[1] / "app"
    violations: list[str] = []
    for source_path in app_root.rglob("*.py"):
        if source_path == app_root / "core" / "legacy_paths.py":
            continue
        visitor = _GlobalCallVisitor()
        visitor.visit(ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path)))
        violations.extend(f"{source_path.relative_to(app_root)}:{function}:{line}:{method}" for function, line, method in visitor.unmarked_calls)
    assert not violations, "Unscoped global resource calls must be inside explicitly marked legacy paths: " + ", ".join(violations)


def test_registered_business_route_modules_retain_mandatory_owner_aware_dependencies() -> None:
    for module in (upload_routes, search_routes, chat_routes):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "get_current_user" in source
        assert "get_db" in source
        assert "legacy_global_resource_path" not in source


def test_owner_aware_file_resolution_cannot_resolve_legacy_root_upload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    owner_id = UUID("30000000-0000-0000-0000-000000000003")
    file_id = "legacy-file-id"
    legacy_file = tmp_path / f"{file_id}.png"
    legacy_file.write_bytes(b"legacy root data")
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    class Authority:
        def require_owned_resource(self, **_kwargs) -> None:
            return None

    monkeypatch.setattr(file_handler, "OwnershipService", lambda _db: Authority())
    with pytest.raises(FileNotFoundError):
        file_handler.resolve_upload_file_owned(object(), owner_id, file_id, ".png")


def test_legacy_marker_is_a_noop_and_does_not_wrap_runtime_behavior() -> None:
    def sample() -> str:
        return "unchanged"

    marked = legacy_global_resource_path("test")(sample)
    assert marked is sample
    assert marked() == "unchanged"
    assert marked.__legacy_global_resource_path__ == "test"
