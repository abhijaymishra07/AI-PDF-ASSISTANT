import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.app.config import settings
from backend.app.deps import rag
from backend.app.models.schemas import DocumentsResponse, UploadResponse

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        size = 0
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                Path(tmp.name).unlink(missing_ok=True)
                raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB limit.")
            tmp.write(chunk)
        tmp_path = Path(tmp.name)

    try:
        meta = rag.ingest_pdf(tmp_path, file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    finally:
        tmp_path.unlink(missing_ok=True)

    return UploadResponse(
        doc_id=meta["doc_id"],
        filename=meta["filename"],
        pages=meta["pages"],
        chunks=meta["chunks"],
        ocr_used=meta.get("ocr_used", False),
    )


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    try:
        rag.delete_document(doc_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {"ok": True, "doc_id": doc_id}


@router.get("/documents", response_model=DocumentsResponse)
def list_documents():
    return DocumentsResponse(documents=rag.list_documents())


@router.get("/documents/{doc_id}/file")
def download_document(doc_id: str):
    meta = rag.documents.get(doc_id)
    if not meta:
        raise HTTPException(404, "Document not found.")
    path = Path(meta["path"])
    if not path.exists():
        raise HTTPException(404, "File missing on disk.")
    return FileResponse(path, media_type="application/pdf", filename=meta["filename"])
