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
          <div className="icon">💬</div>
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
