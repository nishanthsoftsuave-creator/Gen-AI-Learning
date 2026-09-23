import { useRef, useState } from "react";

export default function InputBar({ onSend, disabled }) {
  const [value, setValue] = useState("");
  const textareaRef = useRef(null);

  function resize() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }

  function handleSend() {
    const question = value.trim();
    if (!question) return;
    onSend(question);
    setValue("");
    requestAnimationFrame(() => {
      if (textareaRef.current) textareaRef.current.style.height = "auto";
    });
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="input-bar">
      <div className="input-row">
        <textarea
          ref={textareaRef}
          placeholder="Ask a question about your document..."
          rows={1}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            resize();
          }}
          onKeyDown={handleKeyDown}
        />
        <button
          className="send-btn"
          type="button"
          disabled={disabled}
          title="Send"
          onClick={handleSend}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </div>
      <div className="input-hint">Press Enter to send &middot; Shift+Enter for new line</div>
    </div>
  );
}
