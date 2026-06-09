"""
AI PDF Assistant — Streamlit deployment entry point.
Deploy on Streamlit Community Cloud: https://share.streamlit.io
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Project root on PYTHONPATH for backend imports
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Writable dirs on Streamlit Cloud (ephemeral)
_DATA = Path(os.environ.get("STREAMLIT_DATA_DIR", "/tmp/pdf-assistant"))
os.environ.setdefault("UPLOAD_DIR", str(_DATA / "uploads"))
os.environ.setdefault("VECTOR_DIR", str(_DATA / "vectorstore"))
os.environ.setdefault("OCR_ENABLED", "false")


def _apply_streamlit_secrets() -> list[str]:
    """Map Streamlit Cloud secrets → os.environ. Returns list of keys applied."""
    applied: list[str] = []
    try:
        import streamlit as st

        secrets = st.secrets

        def _set(name: str, value) -> None:
            if value is not None and str(value).strip():
                os.environ[name] = str(value).strip()
                applied.append(name)

        # Top-level keys
        for key in (
            "LLM_PROVIDER",
            "GROQ_API_KEY",
            "GROQ_MODEL",
            "GROQ_MODEL_MATH",
            "GEMINI_API_KEY",
            "GEMINI_MODEL",
        ):
            if key in secrets:
                _set(key, secrets[key])

        # Common nested sections users create by mistake
        for section in ("general", "secrets", "groq", "api"):
            if section in secrets:
                block = secrets[section]
                for k, v in block.items():
                    _set(k.upper(), v)

        # Entire .env pasted as multiline string under one key
        if "env" in secrets:
            for line in str(secrets["env"]).splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    _set(k.strip().upper(), v.strip().strip('"').strip("'"))

    except Exception:
        pass
    return applied


import streamlit as st

st.set_page_config(
    page_title="AI PDF Assistant",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Bump when backend RAG API changes so Streamlit Cloud drops stale cached instances.
_RAG_CACHE_VERSION = "compare-v3"


@st.cache_resource(show_spinner="Loading AI models (first run may take 1–2 min)…")
def get_rag(_cache_version: str = _RAG_CACHE_VERSION):
    _apply_streamlit_secrets()
    from backend.app.deps import rag

    Path(os.environ["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(os.environ["VECTOR_DIR"]).mkdir(parents=True, exist_ok=True)
    return rag


def _rag_chat(rag, question: str, doc_ids: list[str] | None, compare_mode: bool):
    """Call rag.chat; supports older deployments without compare_mode."""
    import inspect

    params = inspect.signature(rag.chat).parameters
    if "compare_mode" in params:
        return rag.chat(question, doc_ids, compare_mode=compare_mode)
    if compare_mode and doc_ids and len(doc_ids) > 1:
        return rag.chat(question, doc_ids)
    return rag.chat(question, doc_ids)


def _api_key_ok() -> bool:
    _apply_streamlit_secrets()
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    if provider == "groq":
        key = os.environ.get("GROQ_API_KEY", "")
        return bool(key and not key.startswith("your-"))
    if provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY", "")
        return bool(key and not key.startswith("your-"))
    return True


def _ingest_upload(rag, uploaded) -> dict:
    max_mb = int(os.environ.get("MAX_UPLOAD_MB", "15"))
    data = uploaded.getvalue()
    if len(data) > max_mb * 1024 * 1024:
        raise ValueError(f"File exceeds {max_mb} MB limit.")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        return rag.ingest_pdf(tmp_path, uploaded.name)
    finally:
        tmp_path.unlink(missing_ok=True)


def sidebar_upload(rag) -> None:
    """Upload + auto-index in sidebar."""
    st.sidebar.subheader("⬆ Upload PDF")
    st.sidebar.caption("Max 15 MB · indexes automatically")
    uploaded = st.sidebar.file_uploader("Choose PDF", type=["pdf"], key="pdf_upload", label_visibility="collapsed")
    if uploaded is not None:
        token = f"{uploaded.name}:{uploaded.size}"
        if st.session_state.get("indexed_token") != token:
            with st.sidebar.spinner("Indexing…"):
                try:
                    meta = _ingest_upload(rag, uploaded)
                    st.session_state.indexed_token = token
                    st.sidebar.success(f"✓ {meta['filename']} ({meta['pages']} pages)")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(str(e))


def sidebar_documents(rag) -> list[str]:
    st.sidebar.header("📚 Documents")
    docs = rag.list_documents()
    if not docs:
        st.sidebar.info("Upload a PDF to get started.")
        return []

    options = {f"{d.filename} ({d.pages} pg)": d.doc_id for d in docs}
    labels = list(options.keys())
    selected_labels = st.sidebar.multiselect(
        "Active for chat / summary",
        labels,
        default=labels[:1] if labels else [],
    )
    selected_ids = [options[l] for l in selected_labels]

    with st.sidebar.expander("Manage documents"):
        for d in docs:
            c1, c2 = st.sidebar.columns([3, 1])
            c1.caption(f"`{d.doc_id}` · {d.chunks} chunks")
            if c2.button("🗑", key=f"del_{d.doc_id}", help="Delete"):
                try:
                    rag.delete_document(d.doc_id)
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(str(e))

    return selected_ids


def tab_chat(rag, doc_ids: list[str]):
    st.subheader("Chat with your PDFs")
    compare = st.checkbox("Compare mode (needs 2+ documents selected in sidebar)")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("citations"):
                with st.expander("Sources"):
                    for c in msg["citations"]:
                        st.caption(
                            f"**{c.doc_id}** page {c.page} · score {c.score:.2f}"
                        )
                        st.text(c.snippet[:400])

    if not doc_ids:
        st.warning("Select at least one document in the sidebar.")
        return

    question = st.chat_input("Ask about your documents…")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                try:
                    if compare and len(doc_ids) < 2:
                        st.error("Compare mode needs 2+ documents selected in the sidebar.")
                        return
                    answer, citations = _rag_chat(
                        rag,
                        question,
                        doc_ids or None,
                        compare_mode=compare,
                    )
                    st.markdown(answer)
                    if citations:
                        with st.expander("Sources"):
                            for c in citations:
                                st.caption(
                                    f"**{c.doc_id}** page {c.page} · score {c.score:.2f}"
                                )
                                st.text(c.snippet[:400])
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": answer,
                            "citations": citations,
                        }
                    )
                except Exception as e:
                    import traceback
                    st.error(str(e))
                    with st.expander("Error details"):
                        st.code(traceback.format_exc())


def tab_summary(rag, doc_ids: list[str]):
    st.subheader("Summarize")
    if not doc_ids:
        st.warning("Select a document in the sidebar.")
        return
    doc_id = doc_ids[0] if len(doc_ids) == 1 else st.selectbox(
        "Document",
        doc_ids,
        format_func=lambda i: rag.documents.get(i, {}).get("filename", i),
    )
    mode = st.selectbox("Mode", ["short", "detailed", "bullets"])
    if st.button("Generate summary", type="primary"):
        with st.spinner("Summarizing…"):
            try:
                text = rag.summarize(doc_id, mode)
                st.markdown(text)
                st.session_state.last_summary = text
            except Exception as e:
                st.error(str(e))


def tab_search(rag, doc_ids: list[str]):
    st.subheader("Keyword search")
    q = st.text_input("Search term")
    scope = st.radio("Scope", ["Selected documents", "All documents"], horizontal=True)
    if st.button("Search", type="primary") and q:
        with st.spinner("Searching…"):
            try:
                ids = doc_ids if scope.startswith("Selected") and doc_ids else None
                hits = rag.keyword_search(q, ids)
                if not hits:
                    st.info("No matches.")
                    return
                for h in hits:
                    st.markdown(f"**{h.doc_id}** · page {h.page} · score {h.score:.2f}")
                    st.caption(h.snippet)
            except Exception as e:
                st.error(str(e))


def tab_quiz(rag, doc_ids: list[str]):
    st.subheader("Quiz generator")
    if not doc_ids:
        st.warning("Select a document in the sidebar.")
        return
    doc_id = doc_ids[0]
    n = st.slider("Number of questions", 3, 10, 5)
    if st.button("Generate quiz", type="primary"):
        with st.spinner("Creating quiz…"):
            try:
                questions = rag.generate_quiz(doc_id, n)
                for i, q in enumerate(questions, 1):
                    st.markdown(f"**Q{i}.** {q.get('question', '')}")
                    for opt in q.get("options", []):
                        st.markdown(f"- {opt}")
                    with st.expander("Answer"):
                        st.markdown(f"**{q.get('answer', '')}** — {q.get('explanation', '')}")
            except Exception as e:
                msg = str(e)
                if "429" in msg or "rate limit" in msg.lower():
                    st.error(
                        "Groq rate limit reached. Wait 30–60 seconds, then try again "
                        "with fewer questions (5 instead of 10)."
                    )
                else:
                    st.error(msg)


def tab_utilities(rag):
    st.subheader("PDF utilities")
    util = st.selectbox(
        "Tool",
        ["Merge PDFs", "Split PDF", "Compress", "Convert to TXT", "Password protect"],
    )

    from backend.app.services import pdf_tools

    if util == "Merge PDFs":
        files = st.file_uploader("PDFs to merge (2+)", type=["pdf"], accept_multiple_files=True)
        if files and len(files) >= 2 and st.button("Merge"):
            pdfs = [f.getvalue() for f in files]
            out = pdf_tools.merge_pdfs(pdfs)
            st.download_button("Download merged.pdf", out, "merged.pdf", "application/pdf")

    elif util == "Split PDF":
        f = st.file_uploader("PDF", type=["pdf"], key="split")
        mode = st.selectbox("Mode", ["each", "range"])
        ranges = st.text_input("Ranges (e.g. 1-3,5)") if mode == "range" else ""
        if f and st.button("Split"):
            data, name, mime = pdf_tools.split_pdf(f.getvalue(), mode, ranges)
            st.download_button(f"Download {name}", data, name, mime)

    elif util == "Compress":
        f = st.file_uploader("PDF", type=["pdf"], key="compress")
        if f and st.button("Compress"):
            out = pdf_tools.compress_pdf(f.getvalue())
            st.download_button("Download compressed.pdf", out, "compressed.pdf", "application/pdf")

    elif util == "Convert to TXT":
        f = st.file_uploader("PDF", type=["pdf"], key="txt")
        if f and st.button("Convert"):
            text = pdf_tools.pdf_to_text(f.getvalue())
            st.download_button("Download.txt", text.encode(), "converted.txt", "text/plain")

    elif util == "Password protect":
        f = st.file_uploader("PDF", type=["pdf"], key="protect")
        pw = st.text_input("Password (min 4 chars)", type="password")
        if f and pw and len(pw) >= 4 and st.button("Protect"):
            out = pdf_tools.protect_pdf(f.getvalue(), pw)
            st.download_button("Download protected.pdf", out, "protected.pdf", "application/pdf")


def tab_export(rag, doc_ids: list[str]):
    st.subheader("Export")
    if not doc_ids:
        st.warning("Select a document in the sidebar.")
        return
    doc_id = doc_ids[0]
    summary = st.text_area("Summary text", st.session_state.get("last_summary", ""))
    notes = st.text_area("Extra notes (optional)")
    from backend.app.services import export as export_svc

    c1, c2 = st.columns(2)
    if c1.button("Export DOCX") and summary:
        try:
            data = export_svc.export_notes_docx(doc_id, summary, notes)
            st.download_button("Download DOCX", data, "notes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        except Exception as e:
            st.error(str(e))
    if c2.button("Export PDF report") and summary:
        try:
            title = rag.documents[doc_id]["filename"]
            body = summary + ("\n\n" + notes if notes else "")
            data = export_svc.export_report_pdf(doc_id, title, body)
            st.download_button("Download PDF", data, "report.pdf", "application/pdf")
        except Exception as e:
            st.error(str(e))


def main():
    applied = _apply_streamlit_secrets()

    st.title("📄 AI PDF Assistant")
    st.caption("RAG-powered chat, summaries, quiz & PDF tools")

    if not _api_key_ok():
        st.error("**Groq API key not detected** — the app cannot call the LLM yet.")
        st.markdown(
            """
### Fix in Streamlit Cloud

1. Open [share.streamlit.io](https://share.streamlit.io) → **My apps** → your app → **⋮** → **Settings** → **Secrets**
2. **Delete everything** in the box and paste **only** this (use your real key):

```toml
LLM_PROVIDER = "groq"
GROQ_API_KEY = "gsk_paste_your_key_here"
GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_MODEL_MATH = "llama-3.3-70b-versatile"
```

3. Click **Save** → **⋮** → **Reboot app**

**Common mistakes:** using `.env` format without quotes, putting keys under `[general]` only without top-level names, or pasting your GitHub password instead of the `gsk_...` token.
            """
        )
        with st.expander("Diagnostics (no secrets shown)"):
            st.write("Secrets loaded into env:", applied or "none")
            st.write("GROQ_API_KEY set:", bool(os.environ.get("GROQ_API_KEY")))
            st.write("LLM_PROVIDER:", os.environ.get("LLM_PROVIDER", "(not set)"))
            try:
                st.write("Keys in st.secrets:", list(st.secrets.keys()))
            except Exception as e:
                st.write("Could not read st.secrets:", e)
        st.stop()

    rag = get_rag()

    # Sidebar first — upload + document list
    st.sidebar.title("📄 PDF Assistant")
    sidebar_upload(rag)
    st.sidebar.divider()
    doc_ids = sidebar_documents(rag)
    st.sidebar.divider()
    st.sidebar.caption(
        "Session-only storage on Streamlit Cloud. "
        "[GitHub](https://github.com/abhijaymishra07/AI-PDF-ASSISTANT)"
    )

    tabs = st.tabs(["💬 Chat", "📝 Summary", "🔍 Search", "❓ Quiz", "🛠 Utilities", "📥 Export"])
    with tabs[0]:
        tab_chat(rag, doc_ids)
    with tabs[1]:
        tab_summary(rag, doc_ids)
    with tabs[2]:
        tab_search(rag, doc_ids)
    with tabs[3]:
        tab_quiz(rag, doc_ids)
    with tabs[4]:
        tab_utilities(rag)
    with tabs[5]:
        tab_export(rag, doc_ids)


if __name__ == "__main__":
    main()
