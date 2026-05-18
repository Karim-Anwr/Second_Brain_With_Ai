from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.pipelines.search_pipeline import search_pipeline
from app.core.exceptions import StorageException


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


@router.get("/memories/favorites")
async def get_favorites():
    """جيب كل الـ favorites"""
    try:
        result = search_pipeline.search_by_filter(
            is_favorite=True,
            top_k=20,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))