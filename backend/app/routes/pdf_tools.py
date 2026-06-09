from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from backend.app.services import pdf_tools

router = APIRouter(prefix="/api/utils", tags=["pdf-utils"])


async def _read_pdf(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file.")
    return data


def _file_response(data: bytes, filename: str, media_type: str) -> Response:
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/merge")
async def merge_pdfs(files: list[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(400, "Upload at least 2 PDF files to merge.")
    try:
        pdfs = [await _read_pdf(f) for f in files]
        result = pdf_tools.merge_pdfs(pdfs)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Merge failed: {e}") from e
    return _file_response(result, "merged.pdf", "application/pdf")


@router.post("/split")
async def split_pdf(
    file: UploadFile = File(...),
    mode: str = Form("each"),
    ranges: str = Form(""),
):
    data = await _read_pdf(file)
    try:
        result, filename, media_type = pdf_tools.split_pdf(data, mode, ranges)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Split failed: {e}") from e
    return _file_response(result, filename, media_type)


@router.post("/compress")
async def compress_pdf(file: UploadFile = File(...)):
    data = await _read_pdf(file)
    try:
        result = pdf_tools.compress_pdf(data)
    except Exception as e:
        raise HTTPException(500, f"Compress failed: {e}") from e
    name = (file.filename or "document.pdf").replace(".pdf", "_compressed.pdf")
    return _file_response(result, name, "application/pdf")


@router.post("/convert")
async def convert_pdf(
    file: UploadFile = File(...),
    target: str = Form("txt"),
):
    filename = file.filename or ""
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file.")

    try:
        if target == "txt":
            if not filename.lower().endswith(".pdf"):
                raise HTTPException(400, "TXT conversion requires a PDF file.")
            text = pdf_tools.pdf_to_text(data)
            out_name = filename.rsplit(".", 1)[0] + ".txt"
            return Response(
                content=text.encode("utf-8"),
                media_type="text/plain",
                headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
            )

        if target == "png":
            if not filename.lower().endswith(".pdf"):
                raise HTTPException(400, "PNG conversion requires a PDF file.")
            zip_data = pdf_tools.pdf_to_images_zip(data, "png")
            out_name = filename.rsplit(".", 1)[0] + "_pages.zip"
            return _file_response(zip_data, out_name, "application/zip")

        if target == "pdf-from-images":
            if not pdf_tools.detect_image_type(filename):
                raise HTTPException(400, "Upload PNG/JPG images to create a PDF.")
            result = pdf_tools.images_to_pdf([(filename, data)])
            out_name = filename.rsplit(".", 1)[0] + ".pdf"
            return _file_response(result, out_name, "application/pdf")

        raise HTTPException(400, "target must be: txt, png, or pdf-from-images")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Convert failed: {e}") from e


@router.post("/convert-images")
async def convert_images_to_pdf(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "Upload at least one image.")
    images: list[tuple[str, bytes]] = []
    for f in files:
        if not f.filename or not pdf_tools.detect_image_type(f.filename):
            raise HTTPException(400, f"Unsupported image: {f.filename}")
        data = await f.read()
        if data:
            images.append((f.filename, data))
    try:
        result = pdf_tools.images_to_pdf(images)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Conversion failed: {e}") from e
    return _file_response(result, "converted.pdf", "application/pdf")


@router.post("/protect")
async def protect_pdf(
    file: UploadFile = File(...),
    password: str = Form(...),
    owner_password: str = Form(""),
):
    data = await _read_pdf(file)
    try:
        result = pdf_tools.protect_pdf(data, password, owner_password)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Password protection failed: {e}") from e
    name = (file.filename or "document.pdf").replace(".pdf", "_protected.pdf")
    return _file_response(result, name, "application/pdf")
