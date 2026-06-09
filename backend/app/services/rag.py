from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from backend.app.config import settings
from backend.app.models.schemas import Citation, DocumentInfo, SearchHit
from backend.app.services import llm
from backend.app.services.chunker import chunk_pages
from backend.app.services.math_utils import extract_math_terms, is_math_question
from backend.app.services.pdf_processor import extract_pages
from backend.app.services.vector_store import ChunkMeta, VectorStore

REGISTRY_FILE = "documents.json"


class RAGService:
    def __init__(self) -> None:
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        settings.vector_dir.mkdir(parents=True, exist_ok=True)
        self.store = VectorStore.load()
        self.documents: dict[str, dict] = self._load_registry()

    def _registry_path(self) -> Path:
        return settings.vector_dir / REGISTRY_FILE

    def _load_registry(self) -> dict[str, dict]:
        path = self._registry_path()
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def _save_registry(self) -> None:
        self._registry_path().write_text(
            json.dumps(self.documents, indent=2),
            encoding="utf-8",
        )

    def _persist(self) -> None:
        self.store.save()
        self._save_registry()

    def ingest_pdf(self, file_path: Path, original_name: str) -> dict:
        doc_id = str(uuid.uuid4())[:8]
        dest = settings.upload_dir / f"{doc_id}_{original_name}"
        dest.write_bytes(file_path.read_bytes())

        from pypdf import PdfReader

        reader = PdfReader(str(dest))
        native_pages = sum(
            1 for p in reader.pages if (p.extract_text() or "").strip()
        )

        pages = extract_pages(dest)
        if not pages:
            raise ValueError(
                "No text could be extracted. For scanned PDFs install: "
                "sudo apt install tesseract-ocr poppler-utils && pip install pytesseract pdf2image"
            )

        ocr_used = native_pages == 0 and len(pages) > 0

        chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
        count = self.store.add_document(doc_id, chunks)
        self.documents[doc_id] = {
            "doc_id": doc_id,
            "filename": original_name,
            "pages": len(pages),
            "chunks": count,
            "path": str(dest),
            "ocr_used": ocr_used,
        }
        self._persist()
        return self.documents[doc_id]

    def list_documents(self) -> list[DocumentInfo]:
        return [DocumentInfo(**meta) for meta in self.documents.values()]

    def _build_context(self, hits: list[tuple[ChunkMeta, float]]) -> str:
        blocks = []
        for chunk, score in hits:
            blocks.append(
                f"[doc={chunk.doc_id} page={chunk.page} chunk={chunk.chunk_id} score={score:.3f}]\n{chunk.text}"
            )
        return "\n\n".join(blocks)

    def _hits_to_citations(self, hits: list[tuple[ChunkMeta, float]]) -> list[Citation]:
        return [
            Citation(
                doc_id=c.doc_id,
                page=c.page,
                chunk_id=c.chunk_id,
                snippet=c.text[:300],
                score=score,
            )
            for c, score in hits
        ]

    def _merge_hits(
        self,
        *hit_lists: list[tuple[ChunkMeta, float]],
        limit: int,
    ) -> list[tuple[ChunkMeta, float]]:
        seen: set[tuple[str, int, int]] = set()
        merged: list[tuple[ChunkMeta, float]] = []
        for hits in hit_lists:
            for chunk, score in hits:
                key = (chunk.doc_id, chunk.page, chunk.chunk_id)
                if key in seen:
                    continue
                seen.add(key)
                merged.append((chunk, score))
        merged.sort(key=lambda x: x[1], reverse=True)
        return merged[:limit]

    def _retrieve(self, question: str, doc_ids: list[str] | None, math_mode: bool) -> list[tuple[ChunkMeta, float]]:
        top_k = settings.math_top_k if math_mode else settings.top_k
        if doc_ids and len(doc_ids) > 1:
            top_k = top_k * len(doc_ids)

        vector_hits = self.store.search(question, top_k, doc_ids)

        if not math_mode:
            return vector_hits

        keyword_hits: list[tuple[ChunkMeta, float]] = []
        for term in extract_math_terms(question):
            keyword_hits.extend(self.store.keyword_search(term, limit=5, doc_ids=doc_ids))

        return self._merge_hits(vector_hits, keyword_hits, limit=top_k + 4)

    def _retrieve_balanced(self, question: str, doc_ids: list[str]) -> dict[str, list[tuple[ChunkMeta, float]]]:
        """Retrieve a representative sample from each document for comparison.

        Strategy: spread chunks across pages (beginning, middle, end) so the
        LLM sees the full breadth of each document, then layer on semantic hits
        for any specific topics the user mentioned."""
        budget = max(settings.top_k, 6)
        result: dict[str, list[tuple[ChunkMeta, float]]] = {}

        for did in doc_ids:
            doc_chunks = [c for c in self.store.chunks if c.doc_id == did]
            if not doc_chunks:
                continue

            pages: dict[int, list[ChunkMeta]] = {}
            for c in doc_chunks:
                pages.setdefault(c.page, []).append(c)
            sorted_pages = sorted(pages.keys())
            n_pages = len(sorted_pages)

            if n_pages <= budget:
                selected_pages = sorted_pages
            else:
                indices = set()
                indices.update(range(min(2, n_pages)))
                indices.update(range(max(0, n_pages - 2), n_pages))
                mid = n_pages // 2
                indices.update(range(max(0, mid - 1), min(n_pages, mid + 2)))
                remaining = budget - len(indices)
                if remaining > 0:
                    step = max(1, n_pages // remaining)
                    for i in range(0, n_pages, step):
                        indices.add(i)
                        if len(indices) >= budget:
                            break
                selected_pages = [sorted_pages[i] for i in sorted(indices)]

            sampled: list[tuple[ChunkMeta, float]] = []
            seen: set[tuple[int, int]] = set()
            for pg in selected_pages:
                chunk = pages[pg][0]
                key = (chunk.page, chunk.chunk_id)
                if key not in seen:
                    sampled.append((chunk, 0.0))
                    seen.add(key)

            vector_hits = self.store.search(question, min(budget, 5), [did])
            for chunk, score in vector_hits:
                key = (chunk.page, chunk.chunk_id)
                if key not in seen:
                    sampled.append((chunk, score))
                    seen.add(key)

            sampled.sort(key=lambda x: (x[0].page, x[0].chunk_id))
            result[did] = sampled

        return result

    def _build_compare_context(
        self, per_doc_hits: dict[str, list[tuple[ChunkMeta, float]]]
    ) -> str:
        sections: list[str] = []
        for doc_id, hits in per_doc_hits.items():
            doc_meta = self.documents.get(doc_id, {})
            label = doc_meta.get("filename", doc_id)
            lines = [f"=== Document: {label} (doc_id={doc_id}, {doc_meta.get('pages', '?')} pages) ==="]
            for chunk, score in hits:
                lines.append(f"[page {chunk.page}, chunk {chunk.chunk_id}]\n{chunk.text}")
            sections.append("\n\n".join(lines))
        return "\n\n" + ("\n\n---\n\n".join(sections)) + "\n\n"

    def chat(
        self,
        question: str,
        doc_ids: list[str] | None = None,
        compare_mode: bool = False,
    ) -> tuple[str, list[Citation]]:
        math_mode = is_math_question(question)
        multi = doc_ids and len(doc_ids) > 1

        if compare_mode and multi:
            per_doc_hits = self._retrieve_balanced(question, doc_ids)
            all_hits = [h for hits in per_doc_hits.values() for h in hits]
            if not all_hits:
                return (
                    "No relevant content found. Upload a PDF first or try a different question.",
                    [],
                )
            context = self._build_compare_context(per_doc_hits)
            doc_labels = {
                did: self.documents.get(did, {}).get("filename", did)
                for did in doc_ids
            }
            label_list = ", ".join(f'"{v}" (doc_id={k})' for k, v in doc_labels.items())
            system = (
                "You are an expert document analyst. You compare PDF documents thoroughly and accurately.\n"
                "Rules:\n"
                "1. Use ONLY the provided context excerpts — never invent content.\n"
                "2. Cite every claim as (doc_id, page N).\n"
                "3. Structure your response with clear headings.\n"
                "4. Detect the user's task intent:\n"
                "   - If the user asks for MCQs/quiz/questions for EACH PDF, generate them separately\n"
                "     for each document using ONLY that document's excerpts.\n"
                "     Do NOT mix questions or answers across documents.\n"
                "   - Otherwise, perform a comparison.\n"
                "5. First identify what SUBJECT each document covers (e.g. math, English, science, history).\n"
                "6. If the documents cover different subjects, state that clearly up front.\n"
                "7. For MCQs: include the correct answer and a short explanation grounded in the excerpts.\n"
                "8. For MCQs: after each question or explanation, include the source citation (doc_id, page N).\n"
                "9. For comparison (non-MCQ tasks): if same subject, compare scope/depth, key concepts, overlapping vs unique content,\n"
                "   difficulty level, and writing style.\n"
                "10. Be specific — quote or reference actual content from the excerpts rather than making vague statements.\n"
                "11. Give a brief summary of each document first (or a short doc intro before MCQs) before the main output."
            )
            user = (
                f"Documents being compared: {label_list}\n\n"
                f"Excerpts from each document:\n{context}\n"
                f"User's question: {question}\n\n"
                "If the question is to create MCQs/questions for each PDF, produce separate MCQ sets per document.\n"
                "Otherwise, first summarize each document and then provide a thorough comparison."
            )
            model = settings.groq_model_math if settings.llm_provider.lower() == "groq" else None
            answer = llm.complete(system, user, temperature=0.2, model=model)
            return answer, self._hits_to_citations(all_hits)

        hits = self._retrieve(question, doc_ids, math_mode)

        if not hits:
            return (
                "No relevant content found. Upload a PDF first or try a different question.",
                [],
            )

        context = self._build_context(hits)

        if math_mode:
            system = llm.MATH_SYSTEM_PROMPT
            user = (
                f"PDF context (formulas, examples, definitions):\n{context}\n\n"
                f"Math question:\n{question}\n\n"
                "Solve step by step using the context method where applicable."
            )
            model = settings.groq_model_math if settings.llm_provider.lower() == "groq" else None
            answer = llm.complete(system, user, temperature=0.1, model=model)
        elif multi:
            system = (
                "You compare multiple PDF documents using ONLY the provided context. "
                "Highlight similarities, differences, and cite each doc as (doc_id, page N)."
            )
            user = f"Context from {len(doc_ids)} PDFs:\n{context}\n\nComparison question: {question}"
            answer = llm.complete(system, user)
        else:
            system = llm.SYSTEM_PROMPT
            user = f"Context from PDFs:\n{context}\n\nQuestion: {question}"
            answer = llm.complete(system, user)

        return answer, self._hits_to_citations(hits)

    def generate_quiz(self, doc_id: str, num_questions: int = 5) -> list[dict]:
        if doc_id not in self.documents:
            raise ValueError(f"Document {doc_id} not found.")
        doc_chunks = [c for c in self.store.chunks if c.doc_id == doc_id][:8]
        context = "\n\n".join(f"[page {c.page}]\n{c.text}" for c in doc_chunks)
        user = f"""Create {num_questions} quiz questions from this document.
Return JSON array: [{{"question":"...","options":["A","B","C","D"],"answer":"A","explanation":"..."}}]

Document:
{context}"""
        data = llm.complete_json(
            "You create educational quiz questions from document excerpts only.",
            user,
            temperature=0.3,
        )
        if isinstance(data, dict) and "questions" in data:
            return data["questions"]
        if isinstance(data, list):
            return data
        raise ValueError("Could not parse quiz response")

    def delete_document(self, doc_id: str) -> None:
        if doc_id not in self.documents:
            raise ValueError(f"Document {doc_id} not found.")
        path = Path(self.documents[doc_id].get("path", ""))
        if path.exists():
            path.unlink()
        self.store.remove_document(doc_id)
        del self.documents[doc_id]
        self._persist()

    def summarize(self, doc_id: str, mode: str) -> str:
        if doc_id not in self.documents:
            raise ValueError(f"Document {doc_id} not found.")

        doc_chunks = [c for c in self.store.chunks if c.doc_id == doc_id]
        if not doc_chunks:
            raise ValueError("Document has no indexed chunks.")

        sample = doc_chunks[:12]
        context = "\n\n".join(f"[page {c.page}]\n{c.text}" for c in sample)
        prompts = {
            "short": "Write a 3–5 sentence summary of the document.",
            "detailed": "Write a detailed multi-paragraph summary covering main topics.",
            "bullets": "Write a bullet-point summary of the key points (use - for bullets).",
        }
        instruction = prompts.get(mode, prompts["short"])
        user = f"{instruction}\n\nDocument excerpts:\n{context}"
        return llm.complete(
            "You summarize academic PDFs clearly and accurately. Use only the provided excerpts.",
            user,
        )

    def keyword_search(self, query: str, doc_ids: list[str] | None = None) -> list[SearchHit]:
        hits = self.store.keyword_search(query, limit=20, doc_ids=doc_ids)
        results: list[SearchHit] = []
        for chunk, score in hits:
            snippet = chunk.text
            match = re.search(re.escape(query), snippet, re.IGNORECASE)
            if match:
                start = max(0, match.start() - 60)
                end = min(len(snippet), match.end() + 60)
                snippet = "..." + snippet[start:end] + "..."
            results.append(
                SearchHit(doc_id=chunk.doc_id, page=chunk.page, snippet=snippet, score=score)
            )
        return results
