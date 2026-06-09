from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import faiss
import numpy as np

from backend.app.config import settings
from backend.app.services.embeddings import embed_query, embed_texts


@dataclass
class ChunkMeta:
    doc_id: str
    page: int
    chunk_id: int
    text: str


@dataclass
class VectorStore:
    chunks: list[ChunkMeta] = field(default_factory=list)
    index: faiss.IndexFlatIP | None = None
    _dim: int = 384

    def _normalize(self, vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        return vectors / norms

    def add_document(self, doc_id: str, chunk_dicts: list[dict]) -> int:
        if not chunk_dicts:
            return 0
        texts = [c["text"] for c in chunk_dicts]
        vectors = self._normalize(embed_texts(texts))
        new_chunks = [
            ChunkMeta(
                doc_id=doc_id,
                page=c["page"],
                chunk_id=c["chunk_id"],
                text=c["text"],
            )
            for c in chunk_dicts
        ]
        self.chunks.extend(new_chunks)

        if self.index is None:
            self._dim = vectors.shape[1]
            self.index = faiss.IndexFlatIP(self._dim)
        self.index.add(vectors)
        return len(new_chunks)

    def remove_document(self, doc_id: str) -> None:
        keep = [c for c in self.chunks if c.doc_id != doc_id]
        if len(keep) == len(self.chunks):
            return
        self.chunks = keep
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        if not self.chunks:
            self.index = None
            return
        texts = [c.text for c in self.chunks]
        vectors = self._normalize(embed_texts(texts))
        self._dim = vectors.shape[1]
        self.index = faiss.IndexFlatIP(self._dim)
        self.index.add(vectors)

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_ids: list[str] | None = None,
    ) -> list[tuple[ChunkMeta, float]]:
        if not self.chunks or self.index is None:
            return []
        q = self._normalize(embed_query(query).reshape(1, -1))
        k = min(top_k * 3, len(self.chunks))
        scores, indices = self.index.search(q, k)
        results: list[tuple[ChunkMeta, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx]
            if doc_ids and chunk.doc_id not in doc_ids:
                continue
            results.append((chunk, float(score)))
            if len(results) >= top_k:
                break
        return results

    def keyword_search(
        self,
        query: str,
        limit: int = 20,
        doc_ids: list[str] | None = None,
    ) -> list[tuple[ChunkMeta, float]]:
        q = query.lower()
        hits: list[tuple[ChunkMeta, float]] = []
        for chunk in self.chunks:
            if doc_ids and chunk.doc_id not in doc_ids:
                continue
            text_lower = chunk.text.lower()
            if q in text_lower:
                hits.append((chunk, 1.0))
        hits.sort(key=lambda x: len(x[0].text))
        return hits[:limit]

    def save(self, path: Path | None = None) -> None:
        base = path or settings.vector_dir
        base.mkdir(parents=True, exist_ok=True)
        meta = [
            {
                "doc_id": c.doc_id,
                "page": c.page,
                "chunk_id": c.chunk_id,
                "text": c.text,
            }
            for c in self.chunks
        ]
        (base / "chunks.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        if self.index is not None:
            faiss.write_index(self.index, str(base / "index.faiss"))

    @classmethod
    def load(cls, path: Path | None = None) -> VectorStore:
        base = path or settings.vector_dir
        store = cls()
        meta_path = base / "chunks.json"
        index_path = base / "index.faiss"
        if not meta_path.exists():
            return store
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        store.chunks = [ChunkMeta(**m) for m in meta]
        if index_path.exists() and store.chunks:
            store.index = faiss.read_index(str(index_path))
            store._dim = store.index.d
        return store
