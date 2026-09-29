import { useRef, useState } from "react";

export default function UploadPanel({ onUpload, uploading, uploadStatus }) {
  const [open, setOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [fileName, setFileName] = useState(null);
  const fileInputRef = useRef(null);

  function setFile(file) {
    if (!file) return;
    if (fileInputRef.current) {
      const transfer = new DataTransfer();
      transfer.items.add(file);
      fileInputRef.current.files = transfer.files;
    }
    setFileName(file.name);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) setFile(file);
  }

  function handleUploadClick() {
    const file = fileInputRef.current?.files?.[0];
    onUpload(file);
  }

  return (
    <div className="upload-panel">
      <button type="button" className="upload-toggle" onClick={() => setOpen((v) => !v)}>
        <span>Intake a document</span>
        <span className={`arrow${open ? " open" : ""}`}>▾</span>
      </button>
      <div className={`upload-body${open ? " show" : ""}`}>
        <div
          className={`upload-box${dragging ? " dragging" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
            <path d="M12 3v12m0-12 4.5 4.5M12 3 7.5 7.5" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <p className="upload-box-title">
            {fileName ? fileName : "Drop a PDF here, or click to browse"}
          </p>
          <p className="upload-box-hint">Replaces the currently loaded document.</p>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            hidden
            onChange={(e) => setFile(e.target.files?.[0])}
          />
          <div className="upload-controls" onClick={(e) => e.stopPropagation()}>
            <button type="button" disabled={uploading || !fileName} onClick={handleUploadClick}>
              {uploading ? "Processing…" : "Upload & process"}
            </button>
          </div>
        </div>
        <p className={`status${uploadStatus?.type ? ` ${uploadStatus.type}` : ""}`}>
          {uploadStatus?.text ?? "No document uploaded yet."}
        </p>
      </div>
    </div>
  );
}
