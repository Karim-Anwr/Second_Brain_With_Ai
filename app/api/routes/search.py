from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUser
from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.core.exceptions import InvalidRequestException, ResourceNotFoundException
from app.db.session import get_db
from app.models.api import (
    FavoriteResponse,
    LinkMemoriesResponse,
    RelatedMemoriesResponse,
    SearchResponse,
    error_responses,
)
from app.pipelines.search_pipeline import search_pipeline
from app.services.graph_service import graph_service
from app.services.storage_service import storage_service
from app.services.file_delivery_service import file_delivery_service


router = APIRouter()


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)
    category: str | None = None
    is_favorite: bool | None = None


@router.post("/search", response_model=SearchResponse, responses=error_responses(401, 422, 500, 503))
async def search_memories(
    request: SearchRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    filters = {}
    if request.category:
        filters["category"] = request.category
    if request.is_favorite is not None:
        filters["is_favorite"] = request.is_favorite

    result = search_pipeline.search_owned(
        db=db,
        owner_user_id=current_user.id,
        query=request.query,
        top_k=request.top_k,
        filters=filters or None,
    )
    return {
        "query": result["query"],
        "total": result["total"],
        "results": [
            {
                "memory_id": item.memory_id,
                "file_name": item.file_name,
                "summary": item.summary,
                "matched_text": item.matched_text,
                "tags": item.tags,
                "created_at": item.created_at,
                "scores": {
                    "final": item.final_score,
                    "semantic": item.semantic_score,
                    "recency": item.recency_score,
                    "importance": item.importance_score,
                },
            }
            for item in result["results"]
        ],
        "llm_answer": result["llm_answer"],
    }


class FavoriteRequest(BaseModel):
    memory_id: str = Field(..., min_length=1, max_length=128)
    is_favorite: bool = True


@router.post("/memories/favorite", response_model=FavoriteResponse, responses=error_responses(401, 404, 422, 500, 503))
async def toggle_favorite(
    request: FavoriteRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if not storage_service.set_favorite_owned(db, current_user.id, request.memory_id, request.is_favorite):
        raise ResourceNotFoundException("Memory")
    return {"memory_id": request.memory_id, "is_favorite": request.is_favorite, "status": "updated"}


class LinkMemoriesRequest(BaseModel):
    from_id: str = Field(..., min_length=1, max_length=128)
    to_id: str = Field(..., min_length=1, max_length=128)


@router.get("/memories/{memory_id}/related", response_model=RelatedMemoriesResponse, responses=error_responses(401, 404, 422, 500, 503))
async def get_related_memories(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    memory_id: str,
    depth: int = Query(default=1, ge=1, le=settings.max_graph_depth),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
):
    related = graph_service.get_related_owned(db, current_user.id, memory_id, depth=depth)
    ordered = sorted(related, key=lambda item: (-float(item["score"]), item["memory_id"]))
    start = (page - 1) * page_size
    return {
        "memory_id": memory_id,
        "total": len(ordered),
        "page": page,
        "page_size": page_size,
        "related": ordered[start : start + page_size],
    }


@router.get(
    "/memories/{memory_id}/file",
    response_class=FileResponse,
    responses={
        200: {
            "description": "An authenticated owner-scoped uploaded file.",
            "content": {
                "image/jpeg": {},
                "image/png": {},
                "image/webp": {},
                "application/pdf": {},
            },
        },
        **error_responses(401, 404, 500, 503),
    },
)
async def get_memory_file(
    memory_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    owned_file = file_delivery_service.resolve_owned_memory_file(db, current_user.id, memory_id)
    return FileResponse(
        path=owned_file.path,
        media_type=owned_file.media_type,
        filename=owned_file.download_name,
        content_disposition_type="inline",
    )


@router.post("/memories/link", response_model=LinkMemoriesResponse, responses=error_responses(400, 401, 404, 422, 500, 503))
async def link_memories(
    request: LinkMemoriesRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if request.from_id == request.to_id:
        raise InvalidRequestException("A memory cannot be linked to itself.")
    if not graph_service.add_edge_owned(
        db, current_user.id, request.from_id, request.to_id, relation_type="manual", score=1.0
    ):
        raise InvalidRequestException("The requested memory link is invalid.")
    return {"status": "linked"}
