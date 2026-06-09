import { useState } from "react";
import {
  compressPdf,
  convertImagesToPdf,
  convertPdf,
  downloadBlob,
  fetchDocumentFile,
  mergePdfs,
  protectPdf,
  splitPdf,
} from "../api/client.js";
import FilePicker from "./FilePicker.jsx";
import CustomSelect from "./CustomSelect.jsx";

function LibrarySelect({ documents, value, onChange, disabled }) {
  if (!documents?.length) return null;
  return (
    <CustomSelect
      value={value}
      onChange={onChange}
      disabled={disabled}
      placeholder="— Or pick from uploaded PDFs —"
      options={[
        { value: "", label: "— Or pick from uploaded PDFs —" },
        ...documents.map((d) => ({ value: d.doc_id, label: d.filename })),
      ]}
    />
  );
}

async function resolvePdf(uploadedFile, libraryDocId, documents) {
  if (uploadedFile) return uploadedFile;
  if (!libraryDocId) return null;
  const doc = documents.find((d) => d.doc_id === libraryDocId);
  if (!doc) return null;
  return fetchDocumentFile(libraryDocId, doc.filename);
}

export default function PdfUtilities({
  loading,
  setLoading,
  setError,
  setInfo,
  documents = [],
  selectedDocs = [],
}) {
  const [mergeFiles, setMergeFiles] = useState([]);
  const [splitFile, setSplitFile] = useState(null);
  const [splitLibraryDoc, setSplitLibraryDoc] = useState("");
  const [splitMode, setSplitMode] = useState("each");
  const [splitRanges, setSplitRanges] = useState("");
  const [compressFile, setCompressFile] = useState(null);
  const [compressLibraryDoc, setCompressLibraryDoc] = useState("");
  const [convertFile, setConvertFile] = useState(null);
  const [convertLibraryDoc, setConvertLibraryDoc] = useState("");
  const [convertTarget, setConvertTarget] = useState("txt");
  const [imageFiles, setImageFiles] = useState([]);
  const [protectFile, setProtectFile] = useState(null);
  const [protectLibraryDoc, setProtectLibraryDoc] = useState("");
  const [password, setPassword] = useState("");
  const [ownerPassword, setOwnerPassword] = useState("");

  const selectedLibraryDocs = documents.filter((d) => selectedDocs.includes(d.doc_id));
  const canMergeLibrary = selectedLibraryDocs.length >= 2;

  async function run(action, fn) {
    setLoading(true);
    setError("");
    setInfo("");
    try {
      const { blob, filename } = await fn();
      downloadBlob(blob, filename);
      setInfo(`Downloaded ${filename}`);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || `${action} failed`);
    } finally {
      setLoading(false);
    }
  }

  async function mergeFromLibrary() {
    const files = await Promise.all(
      selectedLibraryDocs.map((d) => fetchDocumentFile(d.doc_id, d.filename))
    );
    return mergePdfs(files);
  }

  return (
    <section className="card">
      <div className="card-header">
        <span className="card-icon">🛠</span>
        <h2>PDF Utilities</h2>
      </div>
      <p className="muted util-intro">
        Pick files with the 📎 buttons below, or use PDFs already uploaded in the sidebar.
      </p>

      <div className="util-grid">
        <div className="util-block">
          <h3>✅ Merge PDFs</h3>
          <p className="muted">Combine 2+ PDFs into one file.</p>
          <FilePicker
            accept=".pdf"
            multiple
            label="Choose 2+ PDF files…"
            files={mergeFiles}
            onChange={setMergeFiles}
            disabled={loading}
          />
          {canMergeLibrary && (
            <p className="muted util-hint">
              {selectedLibraryDocs.length} PDFs selected in sidebar:{" "}
              {selectedLibraryDocs.map((d) => d.filename).join(", ")}
            </p>
          )}
          <div className="util-actions">
            <button
              type="button"
              disabled={loading || mergeFiles.length < 2}
              onClick={() => run("Merge", () => mergePdfs(mergeFiles))}
            >
              Merge uploaded files
            </button>
            {canMergeLibrary && (
              <button
                type="button"
                className="secondary"
                disabled={loading}
                onClick={() => run("Merge", mergeFromLibrary)}
              >
                Merge sidebar selection ({selectedLibraryDocs.length})
              </button>
            )}
          </div>
        </div>

        <div className="util-block">
          <h3>✅ Split PDFs</h3>
          <p className="muted">Every page as ZIP, or custom ranges like 1-3,4-10.</p>
          <LibrarySelect
            documents={documents}
            value={splitLibraryDoc}
            onChange={(id) => {
              setSplitLibraryDoc(id);
              if (id) setSplitFile(null);
            }}
            disabled={loading}
          />
          <FilePicker
            accept=".pdf"
            label="Or choose a PDF file…"
            files={splitFile}
            onChange={(f) => {
              setSplitFile(f);
              if (f) setSplitLibraryDoc("");
            }}
            disabled={loading}
          />
          <CustomSelect
            value={splitMode}
            onChange={setSplitMode}
            disabled={loading}
            options={[
              { value: "each", label: "Each page → ZIP" },
              { value: "range", label: "Custom ranges" },
            ]}
          />
          {splitMode === "range" && (
            <input placeholder="e.g. 1-3,5,7-10" value={splitRanges} onChange={(e) => setSplitRanges(e.target.value)} />
          )}
          <button
            type="button"
            disabled={loading || (!splitFile && !splitLibraryDoc)}
            onClick={() =>
              run("Split", async () => {
                const file = await resolvePdf(splitFile, splitLibraryDoc, documents);
                if (!file) throw new Error("Choose a PDF first.");
                return splitPdf(file, splitMode, splitRanges);
              })
            }
          >
            Split & Download
          </button>
        </div>

        <div className="util-block">
          <h3>✅ Compress PDFs</h3>
          <p className="muted">Reduce file size with cleanup & compression.</p>
          <LibrarySelect
            documents={documents}
            value={compressLibraryDoc}
            onChange={(id) => {
              setCompressLibraryDoc(id);
              if (id) setCompressFile(null);
            }}
            disabled={loading}
          />
          <FilePicker
            accept=".pdf"
            label="Or choose a PDF file…"
            files={compressFile}
            onChange={(f) => {
              setCompressFile(f);
              if (f) setCompressLibraryDoc("");
            }}
            disabled={loading}
          />
          <button
            type="button"
            disabled={loading || (!compressFile && !compressLibraryDoc)}
            onClick={() =>
              run("Compress", async () => {
                const file = await resolvePdf(compressFile, compressLibraryDoc, documents);
                if (!file) throw new Error("Choose a PDF first.");
                return compressPdf(file);
              })
            }
          >
            Compress & Download
          </button>
        </div>

        <div className="util-block">
          <h3>✅ Convert PDFs</h3>
          <p className="muted">PDF → TXT or PNG pages (ZIP).</p>
          <LibrarySelect
            documents={documents}
            value={convertLibraryDoc}
            onChange={(id) => {
              setConvertLibraryDoc(id);
              if (id) setConvertFile(null);
            }}
            disabled={loading}
          />
          <FilePicker
            accept=".pdf"
            label="Or choose a PDF file…"
            files={convertFile}
            onChange={(f) => {
              setConvertFile(f);
              if (f) setConvertLibraryDoc("");
            }}
            disabled={loading}
          />
          <CustomSelect
            value={convertTarget}
            onChange={setConvertTarget}
            disabled={loading}
            options={[
              { value: "txt", label: "PDF → TXT" },
              { value: "png", label: "PDF → PNG (ZIP)" },
            ]}
          />
          <button
            type="button"
            disabled={loading || (!convertFile && !convertLibraryDoc)}
            onClick={() =>
              run("Convert", async () => {
                const file = await resolvePdf(convertFile, convertLibraryDoc, documents);
                if (!file) throw new Error("Choose a PDF first.");
                return convertPdf(file, convertTarget);
              })
            }
          >
            Convert & Download
          </button>
        </div>

        <div className="util-block">
          <h3>✅ Images → PDF</h3>
          <p className="muted">Combine PNG/JPG images into one PDF.</p>
          <FilePicker
            accept="image/*"
            multiple
            label="Choose image files…"
            files={imageFiles}
            onChange={setImageFiles}
            disabled={loading}
          />
          <button
            type="button"
            disabled={loading || imageFiles.length === 0}
            onClick={() => run("Convert", () => convertImagesToPdf(imageFiles))}
          >
            Create PDF
          </button>
        </div>

        <div className="util-block">
          <h3>✅ Password protection</h3>
          <p className="muted">Encrypt with AES-256. You’ll need the password to open the file.</p>
          <LibrarySelect
            documents={documents}
            value={protectLibraryDoc}
            onChange={(id) => {
              setProtectLibraryDoc(id);
              if (id) setProtectFile(null);
            }}
            disabled={loading}
          />
          <FilePicker
            accept=".pdf"
            label="Or choose a PDF file…"
            files={protectFile}
            onChange={(f) => {
              setProtectFile(f);
              if (f) setProtectLibraryDoc("");
            }}
            disabled={loading}
          />
          <input type="password" placeholder="Password (min 4 chars)" value={password} onChange={(e) => setPassword(e.target.value)} />
          <input type="password" placeholder="Owner password (optional)" value={ownerPassword} onChange={(e) => setOwnerPassword(e.target.value)} />
          <button
            type="button"
            disabled={loading || (!protectFile && !protectLibraryDoc) || password.length < 4}
            onClick={() =>
              run("Protect", async () => {
                const file = await resolvePdf(protectFile, protectLibraryDoc, documents);
                if (!file) throw new Error("Choose a PDF first.");
                return protectPdf(file, password, ownerPassword);
              })
            }
          >
            Protect & Download
          </button>
        </div>
      </div>
    </section>
  );
}
