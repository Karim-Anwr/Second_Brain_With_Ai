from pydantic import BaseModel, Field

class SearchRequest(BaseModel):
    query:  str   = Field(..., min_length=1, max_length=500)
    top_k:  int   = Field(default=5, ge=1, le=20)

class SearchResult(BaseModel):
    chunk_id:   str
    text:       str
    file_name:  str
    file_path:  str
    score:      float   # كلما اتقرب من 1، كلما النتيجة أدق

class SearchResponse(BaseModel):
    query:    str
    results:  list[SearchResult]
    total:    int