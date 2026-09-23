import { useRef, useState } from "react";

export default function UploadPanel({ onUpload, uploading, uploadStatus }) {
  const [open, setOpen] = useState(false);
  const fileInputRef = useRef(null);

  function handleUploadClick() {
    const file = fileInputRef.current?.files?.[0];
    onUpload(file);
  }

  return (
    <div className="upload-panel">
      <div className="upload-toggle" onClick={() => setOpen((v) => !v)}>
        <span>Upload a PDF document</span>
        <span className={`arrow${open ? " open" : ""}`}>▼</span>
      </div>
      <div className={`upload-body${open ? " show" : ""}`}>
        <div className="upload-box">
          <p style={{ margin: "0 0 8px", fontSize: "0.9rem" }}>
            Choose a PDF. It will replace the currently loaded document.
          </p>
          <input ref={fileInputRef} type="file" accept="application/pdf" />
          <div className="upload-controls">
            <button type="button" disabled={uploading} onClick={handleUploadClick}>
              Upload &amp; process
            </button>
          </div>
          <p className={`status${uploadStatus?.type ? ` ${uploadStatus.type}` : ""}`}>
            {uploadStatus?.text ?? "No document uploaded yet."}
          </p>
        </div>
      </div>
    </div>
  );
}
