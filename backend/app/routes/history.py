from fastapi import APIRouter, Depends, HTTPException

from backend.app.deps_auth import get_current_user
from backend.app.models.schemas import ChatHistoryResponse, ChatMessagesResponse, ChatSession, ChatMessageItem
from backend.app.services import history as history_service

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/sessions", response_model=ChatHistoryResponse)
def list_sessions(user: dict = Depends(get_current_user)):
    sessions = history_service.list_sessions(user["id"])
    return ChatHistoryResponse(
        sessions=[ChatSession(**s) for s in sessions]
    )


@router.get("/sessions/{session_id}", response_model=ChatMessagesResponse)
def get_session_messages(session_id: str, user: dict = Depends(get_current_user)):
    messages = history_service.get_messages(session_id, user["id"])
    if not messages:
        raise HTTPException(404, "Session not found")
    return ChatMessagesResponse(
        messages=[ChatMessageItem(**m) for m in messages]
    )
