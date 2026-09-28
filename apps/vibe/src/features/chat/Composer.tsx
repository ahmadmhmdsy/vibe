// apps/vibe/src/features/chat/Composer.tsx
import { useState } from "react";
import { api } from "../../lib/api";
import { useChatStore } from "./store";

export function Composer({ sessionId }: { sessionId: string }) {
  const [text, setText] = useState("");
  const { addMessage, setStreaming } = useChatStore();
  const send = async () => {
    if (!text.trim()) return;
    addMessage({ role: "user", content: text });
    setText("");
    setStreaming(true);
    try {
      await api.sendMessage(sessionId, text);
    } finally {
      setStreaming(false);
    }
  };
  return (
    <div style={{ display: "flex", gap: 8, padding: 8 }}>
      <input
        role="textbox"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && send()}
        placeholder="Describe the app you want to build..."
        style={{ flex: 1 }}
      />
      <button onClick={send} disabled={!text.trim()}>Send</button>
    </div>
  );
}
