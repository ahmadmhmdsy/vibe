// apps/vibe/src/features/chat/MessageList.tsx
import { useEffect } from "react";
import { api } from "../../lib/api";
import { SSEClient } from "../../lib/sse";
import { useChatStore } from "./store";

export function MessageList({ sessionId }: { sessionId: string }) {
  const { messages, appendChunk } = useChatStore();
  useEffect(() => {
    const sse = new SSEClient(import.meta.env.VITE_API_URL ?? "http://localhost:8000");
    sse.connect(sessionId, (e) => {
      if (e.type === "text_chunk") appendChunk(e.payload.text as string);
    });
    return () => sse.disconnect();
  }, [sessionId]);
  return (
    <div style={{ flex: 1, overflow: "auto", padding: 8 }}>
      {messages.map((m, i) => (
        <div key={i} style={{ marginBottom: 8 }}>
          <strong>{m.role}:</strong> {m.content}
        </div>
      ))}
    </div>
  );
}
