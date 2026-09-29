// apps/vibe/src/features/chat/MessageList.tsx
import { useEffect, useRef, useState } from "react";
import { api, type Approval } from "../../lib/api";
import { SSEClient } from "../../lib/sse";
import { useChatStore } from "./store";
import { useShallow } from "zustand/react/shallow";
import { Spinner } from "../../components/ui/Spinner";
import { Markdown } from "../../lib/markdown";
import "./chat.css";

export function MessageList({ sessionId }: { sessionId: string }) {
  // useShallow: the selector derives a new array when the session is empty;
  // shallow comparison keeps zustand from looping on the fresh reference.
  const messages = useChatStore(useShallow((s) => s.messagesBySession[sessionId] ?? []));
  const isStreaming = useChatStore((s) => s.isStreamingBySession[sessionId] ?? false);
  const appendChunk = useChatStore((s) => s.appendChunk);
  const setStreaming = useChatStore((s) => s.setStreaming);
  const loadHistory = useChatStore((s) => s.loadHistory);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.listApprovals(sessionId).then(setApprovals).catch(() => {});
  }, [sessionId]);

  // Load persisted history for this session (once per session switch).
  useEffect(() => {
    loadHistory(sessionId).catch(() => {});
  }, [sessionId]);

  // Auto-scroll to the newest message / streaming chunk.
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, isStreaming]);

  useEffect(() => {
    const sse = new SSEClient(import.meta.env.VITE_API_URL ?? "http://localhost:8000");
    sse.connect(sessionId, (e) => {
      if (e.type === "text_chunk") appendChunk(sessionId, e.payload.text as string);
      if (e.type === "turn_complete") setStreaming(sessionId, false);
    });
    return () => sse.disconnect();
  }, [sessionId]);

  return (
    <div role="log" aria-live="polite" className="message-list" ref={listRef}>
      {messages.length === 0 && !isStreaming && (
        <div className="message-empty muted">
          Describe the app you want to build — the agent handles the rest.
        </div>
      )}
      {messages.map((m, i) => (
        <div key={i} className={m.role === "user" ? "message message-user" : "message message-assistant"}>
          <span className="message-role">{m.role === "user" ? "You" : "Agent"}</span>
          <div className="message-content">
            {m.role === "assistant" ? <Markdown content={m.content} /> : m.content}
          </div>
        </div>
      ))}
      {isStreaming && (
        <div className="message-streaming">
          <Spinner size="sm" label="Agent is working" />
          <span>Agent is working...</span>
        </div>
      )}
      {approvals.map((a) => (
        <div key={a.id} className="approval-card" data-status={a.status}>
          <div className="approval-title">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <path d="M8 1.5L15 14H1L8 1.5z" strokeLinejoin="round" />
              <path d="M8 6.5v3" strokeLinecap="round" />
              <circle cx="8" cy="11.2" r="0.4" fill="currentColor" />
            </svg>
            Approval needed
          </div>
          <div className="approval-packages">
            {a.packages.map((p) => (
              <span key={p} className="approval-package">{p}</span>
            ))}
          </div>
          <div className="approval-hint">The agent wants to install these packages.</div>
          <div className="approval-actions">
            <button onClick={() => api.approve(a.id).then(() => setApprovals((prev) => prev.filter((x) => x.id !== a.id)))}>Approve</button>
            <button onClick={() => api.deny(a.id).then(() => setApprovals((prev) => prev.filter((x) => x.id !== a.id)))}>Deny</button>
          </div>
        </div>
      ))}
    </div>
  );
}
