from fastapi import APIRouter, Query

from backend.app.models.schemas import SearchResponse
from backend.app.deps import rag

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search(q: str = Query(..., min_length=2)):
    results = rag.keyword_search(q)
    return SearchResponse(results=results)
