import httpx
from fastapi import APIRouter, HTTPException

from backend.app.deps import rag
from backend.app.models.schemas import QuizRequest, QuizResponse, QuizQuestion
from backend.app.services.llm import LLMError

router = APIRouter(prefix="/api", tags=["quiz"])


@router.post("/quiz", response_model=QuizResponse)
def generate_quiz(body: QuizRequest):
    try:
        questions = rag.generate_quiz(body.doc_id, body.num_questions)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    except LLMError as e:
        raise HTTPException(503, str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(503, f"LLM request failed: {e}") from e
    return QuizResponse(
        doc_id=body.doc_id,
        questions=[QuizQuestion(**q) for q in questions],
    )
