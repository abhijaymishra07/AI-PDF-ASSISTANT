import { useCallback, useEffect, useRef, useState } from "react";
import {
  chat,
  deleteDocument,
  downloadBlob,
  exportNotes,
  exportReport,
  generateQuiz,
  getMe,
  getSessionMessages,
  listDocuments,
  listSessions,
  login,
  logout,
  register,
  searchKeyword,
  summarize,
  transcribeAudio,
  uploadPdf,
} from "./api/client.js";
import PdfUtilities from "./components/PdfUtilities.jsx";
import CustomSelect from "./components/CustomSelect.jsx";

const TABS = [
  { id: "Chat", icon: "💬" },
  { id: "Quiz", icon: "📝" },
  { id: "Utilities", icon: "🛠" },
  { id: "Export", icon: "📥" },
  { id: "History", icon: "🕐" },
  { id: "Account", icon: "👤" },
];

export default function App() {
  const [tab, setTab] = useState("Chat");
  const [documents, setDocuments] = useState([]);
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [compareMode, setCompareMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [user, setUser] = useState(null);

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState([]);
  const [sessionId, setSessionId] = useState(null);

  const [summary, setSummary] = useState("");
  const [summaryMode, setSummaryMode] = useState("short");

  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState([]);

  const [quiz, setQuiz] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [historyMessages, setHistoryMessages] = useState([]);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [exportNotesText, setExportNotesText] = useState("");

  const [dragOver, setDragOver] = useState(false);
  const [recording, setRecording] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "dark");
  const mediaRef = useRef(null);
  const chunksRef = useRef([]);
  const fileInputRef = useRef(null);

  const refreshDocs = useCallback(async () => {
    try {
      const data = await listDocuments();
      setDocuments(data.documents || []);
    } catch {
      setDocuments([]);
    }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    refreshDocs();
    getMe().then(setUser).catch(() => setUser(null));
  }, [refreshDocs]);

  function toggleTheme() {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }

  function toggleDoc(docId) {
    setSelectedDocs((prev) =>
      prev.includes(docId) ? prev.filter((d) => d !== docId) : [...prev, docId]
    );
  }

  async function handleUpload(file) {
    if (!file?.name?.toLowerCase().endsWith(".pdf")) {
      setError("Please upload a PDF file.");
      return;
    }
    setLoading(true);
    setError("");
    setInfo("");
    try {
      const res = await uploadPdf(file);
      setSelectedDocs([res.doc_id]);
      await refreshDocs();
      if (res.ocr_used) setInfo("Scanned PDF detected — text extracted via OCR.");
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(docId) {
    if (!confirm("Delete this document?")) return;
    await deleteDocument(docId);
    setSelectedDocs((prev) => prev.filter((d) => d !== docId));
    await refreshDocs();
  }

  async function handleChat(e) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError("");
    setAnswer("");
    setCitations([]);
    try {
      const docIds = selectedDocs.length ? selectedDocs : null;
      const res = await chat(question, docIds, sessionId, compareMode);
      setAnswer(res.answer);
      setCitations(res.citations || []);
      if (res.session_id) setSessionId(res.session_id);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Chat failed");
    } finally {
      setLoading(false);
    }
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setLoading(true);
        try {
          const res = await transcribeAudio(blob);
          setQuestion(res.text);
        } catch (e) {
          setError(e.response?.data?.detail || "Transcription failed");
        } finally {
          setLoading(false);
        }
      };
      mediaRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setError("Microphone access denied");
    }
  }

  function stopRecording() {
    mediaRef.current?.stop();
    setRecording(false);
  }

  async function handleSummarize() {
    const docId = selectedDocs[0];
    if (!docId) return setError("Select a document first.");
    setLoading(true);
    setError("");
    setSummary("");
    try {
      const res = await summarize(docId, summaryMode);
      setSummary(res.summary);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Summarize failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch(e) {
    e.preventDefault();
    if (searchQ.trim().length < 2) return;
    setLoading(true);
    setError("");
    try {
      const res = await searchKeyword(searchQ);
      setSearchResults(res.results || []);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Search failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleQuiz() {
    const docId = selectedDocs[0];
    if (!docId) return setError("Select a document first.");
    setLoading(true);
    setError("");
    setQuiz([]);
    try {
      const res = await generateQuiz(docId, 5);
      setQuiz(res.questions || []);
      setTab("Quiz");
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Quiz failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleExportDocx() {
    const docId = selectedDocs[0];
    if (!docId || !summary) return setError("Summarize first, then export.");
    setLoading(true);
    try {
      const blob = await exportNotes(docId, summary, exportNotesText);
      downloadBlob(blob, `notes_${docId}.docx`);
    } catch (e) {
      setError(e.response?.data?.detail || "Export failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleExportPdf() {
    const docId = selectedDocs[0];
    if (!docId) return setError("Select a document first.");
    const body = summary || answer || "No content yet.";
    setLoading(true);
    try {
      const blob = await exportReport(docId, "PDF Assistant Report", body);
      downloadBlob(blob, `report_${docId}.pdf`);
    } catch (e) {
      setError(e.response?.data?.detail || "Export failed");
    } finally {
      setLoading(false);
    }
  }

  async function loadHistory() {
    if (!user) return;
    const res = await listSessions();
    setSessions(res.sessions || []);
  }

  async function openSession(id) {
    const res = await getSessionMessages(id);
    setHistoryMessages(res.messages || []);
    setSessionId(id);
  }

  async function handleAuth(isRegister) {
    setLoading(true);
    setError("");
    try {
      const fn = isRegister ? register : login;
      const res = await fn(email, password);
      setUser({ user_id: res.user_id, email: res.email });
      setInfo(isRegister ? "Account created successfully!" : "Welcome back!");
    } catch (e) {
      setError(e.response?.data?.detail || "Auth failed");
    } finally {
      setLoading(false);
    }
  }

  const AskButton = () => (
    <button type="submit" disabled={loading} className={loading ? "btn-loading" : ""}>
      {loading ? <><span className="spinner" /> Thinking…</> : "Ask →"}
    </button>
  );

  return (
    <div className="app-shell">
      <header className="hero">
        <div className="hero-brand">
          <div className="logo">📄</div>
          <div>
            <h1>AI PDF Assistant</h1>
            <p className="subtitle">Upload, chat, summarize & learn from your documents</p>
          </div>
        </div>
        <div className="hero-actions">
          <button
            type="button"
            className="theme-toggle"
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            <span className="theme-toggle-icon">{theme === "dark" ? "☀️" : "🌙"}</span>
            {theme === "dark" ? "Light" : "Dark"}
          </button>
          <span className="status-pill">
            <span className="status-dot" />
            Groq powered
          </span>
        </div>
      </header>

      <nav className="tabs">
        {TABS.map(({ id, icon }) => (
          <button
            key={id}
            type="button"
            className={tab === id ? "tab active" : "tab"}
            onClick={() => {
              setTab(id);
              if (id === "History") loadHistory();
            }}
          >
            {icon} {id}
          </button>
        ))}
      </nav>

      {error && <div className="alert alert-error">⚠ {error}</div>}
      {info && !error && <div className="alert alert-info">ℹ {info}</div>}

      <div className="layout-grid">
        <aside className="sidebar">
          <section className="card">
            <div className="card-header">
              <span className="card-icon">⬆</span>
              <h2>Upload PDF</h2>
            </div>
            <div
              className={`drop-zone ${dragOver ? "dragover" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); handleUpload(e.dataTransfer.files[0]); }}
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="drop-icon">📎</div>
              <div>Drop PDF here or click to browse</div>
              <div className="muted" style={{ fontSize: "0.8rem", marginTop: "0.35rem" }}>Max 15 MB</div>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={(e) => handleUpload(e.target.files[0])}
              disabled={loading}
            />
          </section>

          <section className="card">
            <div className="card-header">
              <span className="card-icon">📚</span>
              <h2>Documents ({documents.length})</h2>
            </div>
            {documents.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">📭</div>
                <p className="muted">No PDFs yet</p>
              </div>
            ) : (
              <ul className="doc-list">
                {documents.map((d) => (
                  <li
                    key={d.doc_id}
                    className={`doc-item ${selectedDocs.includes(d.doc_id) ? "selected" : ""}`}
                  >
                    <label>
                      <input
                        type="checkbox"
                        checked={selectedDocs.includes(d.doc_id)}
                        onChange={() => toggleDoc(d.doc_id)}
                      />
                      <div>
                        <div className="doc-name">{d.filename}</div>
                        <div className="doc-meta">{d.pages} pages · {d.chunks} chunks</div>
                      </div>
                    </label>
                    <button type="button" className="danger small" onClick={() => handleDelete(d.doc_id)}>✕</button>
                  </li>
                ))}
              </ul>
            )}
            <label className="checkbox-row">
              <input type="checkbox" checked={compareMode} onChange={(e) => setCompareMode(e.target.checked)} />
              Compare mode (2+ PDFs)
            </label>
            <label htmlFor="mode">Summary mode</label>
            <CustomSelect
              value={summaryMode}
              onChange={setSummaryMode}
              options={[
                { value: "short", label: "Short" },
                { value: "detailed", label: "Detailed" },
                { value: "bullets", label: "Bullet points" },
              ]}
            />
          </section>
        </aside>

        <main className="main-panel">
          {tab === "Chat" && (
            <>
              <section className="card">
                <div className="card-header">
                  <span className="card-icon">💬</span>
                  <h2>Ask your PDFs</h2>
                </div>
                <form onSubmit={handleChat}>
                  <textarea
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="What would you like to know about your documents?"
                  />
                  <div className="row">
                    <AskButton />
                    {!recording ? (
                      <button type="button" className="secondary" onClick={startRecording}>🎤 Voice</button>
                    ) : (
                      <button type="button" className="recording" onClick={stopRecording}>⏹ Recording…</button>
                    )}
                    <button type="button" className="secondary" onClick={handleSummarize} disabled={loading}>Summarize</button>
                    <button type="button" className="secondary" onClick={handleQuiz} disabled={loading}>Quiz me</button>
                  </div>
                </form>

                {answer && (
                  <div className="answer-box">
                    <span className="answer-label">Answer</span>
                    <p>{answer}</p>
                    {citations.length > 0 && (
                      <div className="citations">
                        {citations.map((c, i) => (
                          <span key={i} className="citation-chip">
                            📄 {c.doc_id} · p.{c.page}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {summary && (
                  <div className="answer-box" style={{ marginTop: "0.75rem" }}>
                    <span className="answer-label">Summary</span>
                    <p>{summary}</p>
                  </div>
                )}
              </section>

              <section className="card">
                <div className="card-header">
                  <span className="card-icon">🔍</span>
                  <h2>Keyword search</h2>
                </div>
                <form onSubmit={handleSearch}>
                  <input
                    value={searchQ}
                    onChange={(e) => setSearchQ(e.target.value)}
                    placeholder="Search across all uploaded PDFs…"
                  />
                  <button type="submit" disabled={loading}>Search</button>
                </form>
                {searchResults.map((r, i) => (
                  <div key={i} className="search-hit">
                    <strong>{r.doc_id}</strong> · page {r.page}
                    <p className="muted" style={{ margin: "0.35rem 0 0" }}>{r.snippet}</p>
                  </div>
                ))}
              </section>
            </>
          )}

          {tab === "Quiz" && (
            <section className="card">
              <div className="card-header">
                <span className="card-icon">📝</span>
                <h2>Quiz</h2>
              </div>
              {quiz.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon">🎯</div>
                  <p className="muted">Select a PDF and click <strong>Quiz me</strong> in Chat</p>
                </div>
              ) : (
                quiz.map((q, i) => (
                  <div key={i} className="quiz-item">
                    <p>
                      <span className="quiz-num">{i + 1}</span>
                      {q.question}
                    </p>
                    <ul>{q.options?.map((o, j) => <li key={j}>{o}</li>)}</ul>
                    <p className="muted">✓ {q.answer} — {q.explanation}</p>
                  </div>
                ))
              )}
            </section>
          )}

          {tab === "Utilities" && (
            <PdfUtilities
              loading={loading}
              setLoading={setLoading}
              setError={setError}
              setInfo={setInfo}
              documents={documents}
              selectedDocs={selectedDocs}
            />
          )}

          {tab === "Export" && (
            <section className="card">
              <div className="card-header">
                <span className="card-icon">📥</span>
                <h2>Export</h2>
              </div>
              <label>Extra notes (optional)</label>
              <textarea
                value={exportNotesText}
                onChange={(e) => setExportNotesText(e.target.value)}
                placeholder="Add your own notes before exporting…"
              />
              <div className="row">
                <button type="button" onClick={handleExportDocx} disabled={loading}>📄 Download DOCX</button>
                <button type="button" className="secondary" onClick={handleExportPdf} disabled={loading}>📑 Download PDF</button>
              </div>
            </section>
          )}

          {tab === "History" && (
            <section className="card">
              <div className="card-header">
                <span className="card-icon">🕐</span>
                <h2>Chat history</h2>
              </div>
              {!user ? (
                <div className="empty-state">
                  <div className="empty-icon">🔐</div>
                  <p className="muted">Sign in under Account to save history</p>
                </div>
              ) : (
                <>
                  <ul className="doc-list">
                    {sessions.map((s) => (
                      <li key={s.id} className="doc-item">
                        <button type="button" className="link" onClick={() => openSession(s.id)}>
                          {s.title || s.id}
                        </button>
                      </li>
                    ))}
                  </ul>
                  {historyMessages.map((m, i) => (
                    <div key={i} className={`history-msg ${m.role}`}>
                      <div className="history-role">{m.role}</div>
                      {m.content.slice(0, 500)}
                    </div>
                  ))}
                </>
              )}
            </section>
          )}

          {tab === "Account" && (
            <section className="card">
              <div className="card-header">
                <span className="card-icon">👤</span>
                <h2>Account</h2>
              </div>
              {user ? (
                <>
                  <div className="account-avatar">{user.email[0].toUpperCase()}</div>
                  <p className="account-email">{user.email}</p>
                  <button type="button" className="secondary" onClick={() => { logout(); setUser(null); }}>
                    Sign out
                  </button>
                </>
              ) : (
                <>
                  <label>Email</label>
                  <input type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
                  <label>Password</label>
                  <input type="password" placeholder="Min. 6 characters" value={password} onChange={(e) => setPassword(e.target.value)} />
                  <div className="row">
                    <button type="button" onClick={() => handleAuth(true)} disabled={loading}>Create account</button>
                    <button type="button" className="secondary" onClick={() => handleAuth(false)} disabled={loading}>Sign in</button>
                  </div>
                </>
              )}
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
