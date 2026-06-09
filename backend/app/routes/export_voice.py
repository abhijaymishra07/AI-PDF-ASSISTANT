from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from backend.app.deps import rag
from backend.app.models.schemas import ExportNotesRequest, ExportReportRequest, TranscribeResponse
from backend.app.services import export as export_service
from backend.app.services.llm import LLMError
from backend.app.services import voice as voice_service

router = APIRouter(prefix="/api", tags=["export-voice"])


@router.post("/export/notes")
def export_notes(body: ExportNotesRequest):
    try:
        data = export_service.export_notes_docx(body.doc_id, body.summary, body.notes)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    filename = f"notes_{body.doc_id}.docx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export/report")
def export_report(body: ExportReportRequest):
    try:
        data = export_service.export_report_pdf(body.doc_id, body.title, body.body)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    filename = f"report_{body.doc_id}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/voice/transcribe", response_model=TranscribeResponse)
async def transcribe(file: UploadFile = File(...)):
    audio = await file.read()
    if not audio:
        raise HTTPException(400, "Empty audio file")
    try:
        text = voice_service.transcribe_audio(audio, file.filename or "audio.webm")
    except LLMError as e:
        raise HTTPException(503, str(e)) from e
    return TranscribeResponse(text=text)
