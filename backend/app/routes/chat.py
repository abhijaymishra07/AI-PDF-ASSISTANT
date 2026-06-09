import httpx
from fastapi import APIRouter, Depends, HTTPException

from backend.app.deps import rag
from backend.app.deps_auth import get_current_user, get_optional_user
from backend.app.models.schemas import ChatRequest, ChatResponse
from backend.app.services import history as history_service
from backend.app.services.llm import LLMError

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    user: dict | None = Depends(get_optional_user),
):
    doc_ids = body.doc_ids
    if body.compare_mode and doc_ids and len(doc_ids) < 2:
        raise HTTPException(400, "Compare mode needs at least 2 documents selected")

    try:
        answer, citations = rag.chat(body.question, doc_ids, compare_mode=body.compare_mode)
    except LLMError as e:
        raise HTTPException(503, str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(503, f"LLM request failed: {e}") from e

    session_id = body.session_id
    if user:
        if not session_id:
            session_id = history_service.create_session(
                user["id"], body.question[:60]
            )
        history_service.save_message(session_id, "user", body.question, user["id"], doc_ids)
        history_service.save_message(session_id, "assistant", answer, user["id"], doc_ids)

    return ChatResponse(answer=answer, citations=citations, session_id=session_id)
