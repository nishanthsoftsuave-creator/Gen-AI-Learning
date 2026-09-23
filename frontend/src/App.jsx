import { useEffect, useState } from "react";
import Header from "./components/Header.jsx";
import UploadPanel from "./components/UploadPanel.jsx";
import ChatArea from "./components/ChatArea.jsx";
import InputBar from "./components/InputBar.jsx";
import AgenticRace from "./components/AgenticRace.jsx";

let nextMessageId = 1;

export default function App() {
  const [view, setView] = useState("qa");
  const [status, setStatus] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [messages, setMessages] = useState([]);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    fetch("/status")
      .then((res) => res.json())
      .then((data) => setStatus(data))
      .catch(() => setStatus({ error: true }));
  }, []);

  async function handleUpload(file) {
    if (!file) {
      setUploadStatus({ type: "error", text: "Please choose a PDF first." });
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setUploading(true);
    setUploadStatus({ type: "", text: "Processing document... this can take a minute." });

    try {
      const res = await fetch("/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed.");

      setStatus({ ready: true, filename: data.filename, chunks: data.chunks });
      setUploadStatus({
        type: "ok",
        text: `Ready: ${data.filename} (${data.chunks} chunks)`,
      });
    } catch (err) {
      setUploadStatus({ type: "error", text: err.message });
    } finally {
      setUploading(false);
    }
  }

  async function handleAsk(question) {
    if (!status?.ready) {
      setMessages((prev) => [
        ...prev,
        { id: nextMessageId++, role: "ai", text: "Please upload a PDF document first.", isMarkdown: false },
      ]);
      return;
    }

    setMessages((prev) => [
      ...prev,
      { id: nextMessageId++, role: "user", text: question, isMarkdown: false },
    ]);
    setAsking(true);

    try {
      const res = await fetch("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not get an answer.");

      setMessages((prev) => [
        ...prev,
        {
          id: nextMessageId++,
          role: "ai",
          text: data.answer,
          isMarkdown: true,
          sources: data.sources,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: nextMessageId++, role: "ai", text: err.message, isMarkdown: false },
      ]);
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="app-shell">
      <Header status={status} view={view} onChangeView={setView} />
      {view === "qa" ? (
        <>
          <UploadPanel onUpload={handleUpload} uploading={uploading} uploadStatus={uploadStatus} />
          <ChatArea messages={messages} asking={asking} />
          <InputBar onSend={handleAsk} disabled={!status?.ready || asking} />
        </>
      ) : (
        <AgenticRace />
      )}
    </div>
  );
}
