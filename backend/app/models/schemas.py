from pydantic import BaseModel, EmailStr, Field


class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    pages: int
    chunks: int
    ocr_used: bool = False


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    doc_ids: list[str] | None = None
    session_id: str | None = None
    compare_mode: bool = False


class Citation(BaseModel):
    doc_id: str
    page: int
    chunk_id: int
    snippet: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    session_id: str | None = None


class SummaryRequest(BaseModel):
    doc_id: str
    mode: str = "short"


class SummaryResponse(BaseModel):
    summary: str
    doc_id: str
    mode: str


class SearchHit(BaseModel):
    doc_id: str
    page: int
    snippet: str
    score: float = 0.0


class SearchResponse(BaseModel):
    results: list[SearchHit]


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    pages: int
    chunks: int


class DocumentsResponse(BaseModel):
    documents: list[DocumentInfo]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user_id: int
    email: str
    access_token: str


class UserResponse(BaseModel):
    user_id: int
    email: str


class QuizRequest(BaseModel):
    doc_id: str
    num_questions: int = Field(default=5, ge=1, le=15)


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    answer: str
    explanation: str = ""


class QuizResponse(BaseModel):
    doc_id: str
    questions: list[QuizQuestion]


class ExportNotesRequest(BaseModel):
    doc_id: str
    summary: str
    notes: str = ""


class ExportReportRequest(BaseModel):
    doc_id: str
    title: str = "PDF Report"
    body: str


class TranscribeResponse(BaseModel):
    text: str


class ChatSession(BaseModel):
    id: str
    title: str
    created_at: str
    last_message: str | None = None


class ChatHistoryResponse(BaseModel):
    sessions: list[ChatSession]


class ChatMessageItem(BaseModel):
    role: str
    content: str
    doc_ids: list[str] | None = None
    created_at: str


class ChatMessagesResponse(BaseModel):
    messages: list[ChatMessageItem]
