from pathlib import Path

from pypdf import PdfReader

from backend.app.config import settings


def _extract_pymupdf(pdf_path: Path) -> list[dict]:
    import fitz

    pages: list[dict] = []
    doc = fitz.open(str(pdf_path))
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if text:
            pages.append({"page": i, "text": _normalize_math_text(text)})
    doc.close()
    return pages


def _normalize_math_text(text: str) -> str:
    """Preserve line breaks around equations; collapse excessive whitespace elsewhere."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Keep short lines (often equations) on their own line
        if len(stripped) < 80 or any(c in stripped for c in "=+∫∑√^"):
            lines.append(stripped)
        else:
            lines.append(" ".join(stripped.split()))
    return "\n".join(lines)


def _ocr_page_image(image) -> str:
    import pytesseract

    return pytesseract.image_to_string(image).strip()


def _extract_with_ocr(pdf_path: Path) -> list[dict]:
    from pdf2image import convert_from_path

    pages: list[dict] = []
    images = convert_from_path(str(pdf_path), dpi=200)
    for i, image in enumerate(images, start=1):
        text = _ocr_page_image(image)
        if text:
            pages.append({"page": i, "text": _normalize_math_text(text)})
    return pages


def _extract_pypdf(pdf_path: Path) -> list[dict]:
    reader = PdfReader(str(pdf_path))
    pages: list[dict] = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page": i, "text": _normalize_math_text(text)})
    return pages


def extract_pages(pdf_path: Path) -> list[dict]:
    """Extract text per page. PyMuPDF first (better for math), then pypdf, then OCR."""
    try:
        pages = _extract_pymupdf(pdf_path)
        if pages:
            return pages
    except ImportError:
        pass
    except Exception:
        pass

    pages = _extract_pypdf(pdf_path)
    if pages or not settings.ocr_enabled:
        return pages

    try:
        return _extract_with_ocr(pdf_path)
    except Exception:
        return []
