// apps/vibe/src/features/chat/MessageList.tsx
import { useEffect, useState } from "react";
import { api, type Approval } from "../../lib/api";
import { SSEClient } from "../../lib/sse";
import { useChatStore } from "./store";
import { Spinner } from "../../components/ui/Spinner";
import "./chat.css";

export function MessageList({ sessionId }: { sessionId: string }) {
  const { messages, appendChunk, isStreaming } = useChatStore();
  const [approvals, setApprovals] = useState<Approval[]>([]);

  useEffect(() => {
    api.listApprovals(sessionId).then(setApprovals).catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    const sse = new SSEClient(import.meta.env.VITE_API_URL ?? "http://localhost:8000");
    sse.connect(sessionId, (e) => {
      if (e.type === "text_chunk") appendChunk(e.payload.text as string);
      if (e.type === "approval") {
        const a = e.payload as unknown as Approval;
        setApprovals((prev) => {
          const idx = prev.findIndex((p) => p.id === a.id);
          if (idx >= 0) {
            const next = [...prev];
            next[idx] = a;
            return next;
          }
          return [...prev, a];
        });
      }
    });
    return () => sse.disconnect();
  }, [sessionId]);

  const resolve = async (a: Approval, approved: boolean) => {
    if (approved) await api.approve(a.id);
    else await api.deny(a.id);
    setApprovals((prev) => prev.map((p) => (p.id === a.id ? { ...p, status: approved ? "approved" : "denied" } : p)));
  };

  return (
    <div role="log" aria-live="polite" className="message-list">
      {messages.length === 0 && !isStreaming && (
        <div className="message-empty muted">
          Describe the app you want to build — the agent handles the rest.
        </div>
      )}
      {messages.map((m, i) => (
        <div key={i} style={{ marginBottom: 8 }}>
          <strong>{m.role}:</strong> {m.content}
        </div>
      ))}
      {isStreaming && (
        <div className="message-streaming">
          <Spinner size="sm" label="Agent is working" />
          <span>Agent is working...</span>
        </div>
      )}
      {approvals.map((a) => (
        <div key={a.id} style={{ marginBottom: 8, padding: 8, border: "1px solid #ccc", borderRadius: 4 }}>
          <div>Agent wants to install: <strong>{a.packages.join(", ")}</strong></div>
          {a.status === "pending" ? (
            <div style={{ marginTop: 4, display: "flex", gap: 8 }}>
              <button onClick={() => resolve(a, true)}>Approve</button>
              <button onClick={() => resolve(a, false)}>Deny</button>
            </div>
          ) : (
            <div style={{ marginTop: 4, color: a.status === "approved" ? "#1a7f37" : "#b3261e" }}>
              {a.status === "approved" ? "Approved" : "Denied"}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
