import httpx
from fastapi import APIRouter, HTTPException

from backend.app.deps import rag
from backend.app.models.schemas import SummaryRequest, SummaryResponse
from backend.app.services.llm import LLMError

router = APIRouter(prefix="/api", tags=["summary"])


@router.post("/summarize", response_model=SummaryResponse)
def summarize(body: SummaryRequest):
    if body.mode not in {"short", "detailed", "bullets"}:
        raise HTTPException(400, "mode must be: short, detailed, bullets")
    try:
        text = rag.summarize(body.doc_id, body.mode)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    except LLMError as e:
        raise HTTPException(503, str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(503, f"LLM request failed: {e}") from e
    return SummaryResponse(summary=text, doc_id=body.doc_id, mode=body.mode)
