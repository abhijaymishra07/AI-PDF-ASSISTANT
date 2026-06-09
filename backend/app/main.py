from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.db.database import init_db
from backend.app.routes import auth, chat, export_voice, history, pdf_tools, quiz, search, summary, upload

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AI PDF Assistant",
    description="Phase 1 + Phase 2: RAG, multi-PDF, quiz, export, voice, auth, history.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(summary.router)
app.include_router(search.router)
app.include_router(auth.router)
app.include_router(history.router)
app.include_router(quiz.router)
app.include_router(export_voice.router)
app.include_router(pdf_tools.router)


@app.get("/")
def root():
    return {"status": "ok", "version": "2.0.0", "docs": "/docs"}
