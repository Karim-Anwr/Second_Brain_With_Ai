from app.services import storage_service
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.pipelines.search_pipeline import search_pipeline
from app.core.exceptions import StorageException
from app.services.graph_service import graph_service



router = APIRouter()


class SearchRequest(BaseModel):
    query:     str  = Field(..., min_length=1, max_length=500)
    top_k:     int  = Field(default=5, ge=1, le=20)
    category:  str  = Field(default=None)
    is_favorite: bool = Field(default=None)


@router.post("/search")
async def search_memories(request: SearchRequest):
    """
    يبحث في الـ memories بسؤال طبيعي.
    مثال: "الحديث اللي كنت حافظه"
    """
    try:
        filters = {}
        if request.category:
            filters["category"] = request.category
        if request.is_favorite is not None:
            filters["is_favorite"] = request.is_favorite

        result = search_pipeline.search(
            query=request.query,
            top_k=request.top_k,
            filters=filters if filters else None,
        )

        return {
            "query":   result["query"],
            "total":   result["total"],
            "results": [
                {
                    "memory_id":    r.memory_id,
                    "file_name":    r.file_name,
                    "file_path":    r.file_path,
                    "summary":      r.summary,
                    "matched_text": r.matched_text,
                    "tags":         r.tags,
                    "created_at":   r.created_at,
                    "scores": {
                        "final":      r.final_score,
                        "semantic":   r.semantic_score,
                        "recency":    r.recency_score,
                        "importance": r.importance_score,
                    }
                }
                for r in result["results"]
            ],
            "llm_answer": result["llm_answer"],  # 📌 هيجي بعدين
        }

    except StorageException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class FavoriteRequest(BaseModel):
    memory_id: str
    is_favorite: bool = True


@router.post("/memories/favorite")
async def toggle_favorite(request: FavoriteRequest):
    """
    يعمل toggle لحالة الـ favorite لذكرى معينة.
    الذكريات المفضلة بتتعلى تلقائياً في ترتيب البحث.
    """
    try:
        success = storage_service.set_favorite(
            memory_id=request.memory_id,
            is_favorite=request.is_favorite,
        )
        if not success:
            raise HTTPException(status_code=404, detail="الذكرى مش موجودة")
        return {
            "memory_id":   request.memory_id,
            "is_favorite": request.is_favorite,
            "status":      "updated",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

class LinkMemoriesRequest(BaseModel):
    from_id: str
    to_id:   str


@router.get("/memories/{memory_id}/related")
async def get_related_memories(memory_id: str, depth: int = 1):
    """
    يجيب الذكريات المرتبطة بذكرى معينة.
    depth=1 → جيران مباشرين، depth=2 → جيران الجيران كمان.
    """
    try:
        related = graph_service.get_related(memory_id, depth=depth)
        return {
            "memory_id": memory_id,
            "total":     len(related),
            "related":   related,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memories/link")
async def link_memories(request: LinkMemoriesRequest):
    """ربط يدوي بين ذكريتين."""
    try:
        success = graph_service.add_edge(
            from_id=request.from_id,
            to_id=request.to_id,
            relation_type="manual",
            score=1.0,
        )
        return {"status": "linked" if success else "failed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))