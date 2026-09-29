import { useEffect, useRef } from "react";
import Message from "./Message.jsx";
import TypingIndicator from "./TypingIndicator.jsx";

export default function ChatArea({ messages, asking }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, asking]);

  return (
    <div className="chat-area" ref={scrollRef}>
      {messages.length === 0 && !asking && (
        <div className="chat-empty">
          <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M6 3h12v14l-4 4v-4H6z" strokeLinejoin="round" />
            <path d="M9 8h6M9 11.5h4" strokeLinecap="round" />
          </svg>
          <p>Upload a PDF, then ask questions about it.</p>
        </div>
      )}
      {messages.map((message) => (
        <Message key={message.id} {...message} />
      ))}
      {asking && <TypingIndicator />}
    </div>
  );
}
