import { renderMarkdown, escapeHtml } from "../lib/markdown.js";

export default function Message({ role, text, isMarkdown, sources }) {
  const html = isMarkdown ? renderMarkdown(text) : `<p>${escapeHtml(text)}</p>`;

  return (
    <div className={`message ${role}`}>
      <div className="avatar">{role === "user" ? "You" : "AI"}</div>
      <div className="bubble">
        <div dangerouslySetInnerHTML={{ __html: html }} />
        {sources && sources.length > 0 && (
          <div className="sources">
            <details>
              <summary>📎 {sources.length} source chunks</summary>
              {sources.map((chunk, idx) => (
                <div className="chunk" key={idx}>
                  Chunk {idx + 1}: {typeof chunk === "string" ? chunk : chunk.text}
                </div>
              ))}
            </details>
          </div>
        )}
      </div>
    </div>
  );
}
