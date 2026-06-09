def chunk_pages(
    pages: list[dict],
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[dict]:
    """
    Split page text into overlapping character chunks.
    Each chunk: {page, text, chunk_id within doc}.
    """
    chunks: list[dict] = []
    chunk_id = 0
    step = max(1, chunk_size - overlap)

    for page_info in pages:
        page_num = page_info["page"]
        text = page_info["text"]
        start = 0
        while start < len(text):
            piece = text[start : start + chunk_size].strip()
            if piece:
                chunks.append(
                    {
                        "page": page_num,
                        "text": piece,
                        "chunk_id": chunk_id,
                    }
                )
                chunk_id += 1
            start += step

    return chunks
