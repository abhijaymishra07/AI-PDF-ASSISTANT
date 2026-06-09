import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export async function uploadPdf(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/upload", form);
  return data;
}

export async function deleteDocument(docId) {
  const { data } = await api.delete(`/documents/${docId}`);
  return data;
}

export async function fetchDocumentFile(docId, filename) {
  const { data } = await api.get(`/documents/${docId}/file`, { responseType: "blob" });
  return new File([data], filename, { type: "application/pdf" });
}

export async function chat(question, docIds = null, sessionId = null, compareMode = false) {
  const { data } = await api.post("/chat", {
    question,
    doc_ids: docIds,
    session_id: sessionId,
    compare_mode: compareMode,
  });
  return data;
}

export async function summarize(docId, mode = "short") {
  const { data } = await api.post("/summarize", { doc_id: docId, mode });
  return data;
}

export async function searchKeyword(q) {
  const { data } = await api.get("/search", { params: { q } });
  return data;
}

export async function listDocuments() {
  const { data } = await api.get("/documents");
  return data;
}

export async function generateQuiz(docId, numQuestions = 5) {
  const { data } = await api.post("/quiz", { doc_id: docId, num_questions: numQuestions });
  return data;
}

export async function register(email, password) {
  const { data } = await api.post("/auth/register", { email, password });
  localStorage.setItem("token", data.access_token);
  return data;
}

export async function login(email, password) {
  const { data } = await api.post("/auth/login", { email, password });
  localStorage.setItem("token", data.access_token);
  return data;
}

export async function logout() {
  localStorage.removeItem("token");
}

export async function getMe() {
  const { data } = await api.get("/auth/me");
  return data;
}

export async function listSessions() {
  const { data } = await api.get("/history/sessions");
  return data;
}

export async function getSessionMessages(sessionId) {
  const { data } = await api.get(`/history/sessions/${sessionId}`);
  return data;
}

export async function transcribeAudio(blob) {
  const form = new FormData();
  form.append("file", blob, "recording.webm");
  const { data } = await api.post("/voice/transcribe", form);
  return data;
}

export async function exportNotes(docId, summary, notes = "") {
  const { data } = await api.post(
    "/export/notes",
    { doc_id: docId, summary, notes },
    { responseType: "blob" }
  );
  return data;
}

export async function exportReport(docId, title, body) {
  const { data } = await api.post(
    "/export/report",
    { doc_id: docId, title, body },
    { responseType: "blob" }
  );
  return data;
}

async function postBlob(url, formData, defaultName) {
  const { data, headers } = await api.post(url, formData, { responseType: "blob" });
  const disposition = headers["content-disposition"] || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : defaultName;
  return { blob: data, filename };
}

export async function mergePdfs(files) {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return postBlob("/utils/merge", form, "merged.pdf");
}

export async function splitPdf(file, mode, ranges = "") {
  const form = new FormData();
  form.append("file", file);
  form.append("mode", mode);
  form.append("ranges", ranges);
  const defaultName = mode === "each" ? "split_pages.zip" : "split.pdf";
  return postBlob("/utils/split", form, defaultName);
}

export async function compressPdf(file) {
  const form = new FormData();
  form.append("file", file);
  const name = file.name.replace(".pdf", "_compressed.pdf");
  return postBlob("/utils/compress", form, name);
}

export async function convertPdf(file, target) {
  const form = new FormData();
  form.append("file", file);
  form.append("target", target);
  const names = { txt: "converted.txt", png: "pages.zip" };
  return postBlob("/utils/convert", form, names[target] || "output");
}

export async function convertImagesToPdf(files) {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return postBlob("/utils/convert-images", form, "converted.pdf");
}

export async function protectPdf(file, password, ownerPassword = "") {
  const form = new FormData();
  form.append("file", file);
  form.append("password", password);
  form.append("owner_password", ownerPassword);
  const name = file.name.replace(".pdf", "_protected.pdf");
  return postBlob("/utils/protect", form, name);
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
