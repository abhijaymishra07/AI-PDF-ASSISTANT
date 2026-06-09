from __future__ import annotations

import io
import re
import zipfile

import fitz


def merge_pdfs(file_bytes_list: list[bytes]) -> bytes:
    if len(file_bytes_list) < 2:
        raise ValueError("Merge requires at least 2 PDF files.")
    merged = fitz.open()
    for data in file_bytes_list:
        src = fitz.open(stream=data, filetype="pdf")
        merged.insert_pdf(src)
        src.close()
    out = io.BytesIO()
    merged.save(out)
    merged.close()
    return out.getvalue()


def _parse_ranges(spec: str, page_count: int) -> list[tuple[int, int]]:
    """Parse '1-3,5,7-10' into 0-indexed (start, end) inclusive ranges."""
    ranges: list[tuple[int, int]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = max(1, int(a.strip()))
            end = min(page_count, int(b.strip()))
        else:
            start = end = max(1, min(page_count, int(part)))
        if start > end:
            raise ValueError(f"Invalid range: {part}")
        ranges.append((start - 1, end - 1))
    if not ranges:
        raise ValueError("No valid page ranges provided.")
    return ranges


def split_pdf(file_bytes: bytes, mode: str, ranges: str = "") -> tuple[bytes, str, str]:
    """
    Returns (data, filename, media_type).
    mode: 'each' = one PDF per page (zip), 'range' = split by ranges (zip if multiple).
    """
    src = fitz.open(stream=file_bytes, filetype="pdf")
    page_count = src.page_count

    if mode == "each":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i in range(page_count):
                part = fitz.open()
                part.insert_pdf(src, from_page=i, to_page=i)
                pb = io.BytesIO()
                part.save(pb)
                part.close()
                zf.writestr(f"page_{i + 1:03d}.pdf", pb.getvalue())
        src.close()
        return buf.getvalue(), "split_pages.zip", "application/zip"

    if mode == "range":
        if not ranges.strip():
            src.close()
            raise ValueError("Provide page ranges, e.g. 1-3,4-10")
        parsed = _parse_ranges(ranges, page_count)
        if len(parsed) == 1:
            start, end = parsed[0]
            part = fitz.open()
            part.insert_pdf(src, from_page=start, to_page=end)
            out = io.BytesIO()
            part.save(out)
            part.close()
            src.close()
            return out.getvalue(), f"pages_{start + 1}-{end + 1}.pdf", "application/pdf"

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, (start, end) in enumerate(parsed, start=1):
                part = fitz.open()
                part.insert_pdf(src, from_page=start, to_page=end)
                pb = io.BytesIO()
                part.save(pb)
                part.close()
                zf.writestr(f"part_{idx}_pages_{start + 1}-{end + 1}.pdf", pb.getvalue())
        src.close()
        return buf.getvalue(), "split_parts.zip", "application/zip"

    src.close()
    raise ValueError("Split mode must be 'each' or 'range'.")


def compress_pdf(file_bytes: bytes) -> bytes:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    out = io.BytesIO()
    doc.save(out, garbage=4, deflate=True, clean=True)
    doc.close()
    return out.getvalue()


def pdf_to_text(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    parts = [page.get_text("text") for page in doc]
    doc.close()
    return "\n\n".join(parts).strip()


def pdf_to_images_zip(file_bytes: bytes, fmt: str = "png") -> bytes:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    buf = io.BytesIO()
    ext = "png" if fmt == "png" else "jpg"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes(ext)
            zf.writestr(f"page_{i + 1:03d}.{ext}", img_bytes)
    doc.close()
    return buf.getvalue()


def images_to_pdf(image_list: list[tuple[str, bytes]]) -> bytes:
    if not image_list:
        raise ValueError("At least one image is required.")
    doc = fitz.open()
    for name, data in image_list:
        suffix = name.rsplit(".", 1)[-1].lower()
        ftype = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
        if ftype not in {"png", "jpeg", "gif", "bmp", "tiff"}:
            ftype = "png"
        img = fitz.open(stream=data, filetype=ftype)
        rect = img[0].rect
        page = doc.new_page(width=rect.width, height=rect.height)
        page.insert_image(rect, stream=data)
        img.close()
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def protect_pdf(file_bytes: bytes, user_password: str, owner_password: str = "") -> bytes:
    if len(user_password) < 4:
        raise ValueError("Password must be at least 4 characters.")
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    perm = int(
        fitz.PDF_PERM_ACCESSIBILITY
        | fitz.PDF_PERM_PRINT
        | fitz.PDF_PERM_COPY
        | fitz.PDF_PERM_ANNOTATE
    )
    out = io.BytesIO()
    doc.save(
        out,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw=user_password,
        owner_pw=owner_password or user_password,
        permissions=perm,
    )
    doc.close()
    return out.getvalue()


def detect_image_type(filename: str) -> bool:
    return bool(re.search(r"\.(png|jpe?g|gif|bmp|tiff?|webp)$", filename, re.I))
