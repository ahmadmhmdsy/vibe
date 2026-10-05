// features/chat/MessageList.tsx — Chat message list with streaming.
// Displays messages, handles SSE events, and shows approval cards.

import { useEffect, useRef, useState } from "react";
import { api, type Approval } from "../../lib/api";
import { SSEClient } from "../../lib/sse";
import { useChatStore } from "./store";
import { useShallow } from "zustand/react/shallow";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { Markdown } from "../../lib/markdown";
import { ApprovalCard } from "./ApprovalCard";
import { usePolling } from "../../hooks/usePolling";
import "./chat.css";

export function MessageList({ sessionId }: { sessionId: string }) {
  const messages = useChatStore(useShallow((s) => s.messagesBySession[sessionId] ?? []));
  const isStreaming = useChatStore((s) => s.isStreamingBySession[sessionId] ?? false);
  const appendChunk = useChatStore((s) => s.appendChunk);
  const endStream = useChatStore((s) => s.endStream);
  const loadHistory = useChatStore((s) => s.loadHistory);
  const loadMoreHistory = useChatStore((s) => s.loadMoreHistory);
  const historyTotal = useChatStore((s) => s.historyTotalBySession[sessionId] ?? 0);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const listRef = useRef<HTMLDivElement>(null);

  // Load persisted history for this session (once per session switch).
  useEffect(() => {
    loadHistory(sessionId).catch(() => {});
  }, [sessionId]);

  // Poll for new approvals
  usePolling(
    async () => {
      const data = await api.listApprovals(sessionId);
      setApprovals(data.filter((a) => a.status === "pending"));
    },
    { interval: 3000, enabled: true }
  );

  // Auto-scroll to the newest message, streaming chunk, or approval — an
  // approval the user cannot see is an approval they cannot answer. Keyed on
  // the last message rather than the whole list, so prepending older messages
  // above does not yank the view back down to the bottom.
  const lastMessage = messages[messages.length - 1];
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lastMessage?.id, lastMessage?.content, isStreaming, approvals]);

  useEffect(() => {
    const sse = new SSEClient(import.meta.env.VITE_API_URL ?? "http://localhost:7321");
    sse.connect(sessionId, (e) => {
      if (e.type === "text_chunk") appendChunk(sessionId, e.payload.text as string);
      if (e.type === "turn_complete") endStream(sessionId);
    });
    return () => sse.disconnect();
  }, [sessionId]);

  const resolveApproval = (id: string) => {
    setApprovals((prev) => prev.filter((x) => x.id !== id));
  };

  return (
    <div role="log" aria-live="polite" className="message-list" ref={listRef}>
      {messages.length === 0 && !isStreaming && (
        <div className="chat-intro">
          <svg className="chat-intro-mark" width="30" height="30" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M3 10l4-4 4 4 4-4 2 2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M3 15l4-4 4 4 4-4 2 2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" opacity="0.4" />
          </svg>
          <h2>Describe the app you want to build</h2>
          <p>
            The agent writes the files, runs the dev server, and shows the result in the preview.
            Dependency installs that fall outside the allowlist wait for your approval.
          </p>
          <div className="chat-intro-hints">
            <span className="chat-intro-hint"><kbd>Enter</kbd> send</span>
            <span className="chat-intro-hint"><kbd>Shift</kbd> + <kbd>Enter</kbd> new line</span>
          </div>
        </div>
      )}
      {historyTotal > messages.length && (
        <div className="message-load-more">
          <Button variant="ghost" size="sm" onClick={() => loadMoreHistory(sessionId).catch(() => {})}>
            Load older messages
          </Button>
        </div>
      )}
      {messages.map((m) => (
        <div key={m.id} className={m.role === "user" ? "message message-user" : "message message-assistant"}>
          <span className="message-role">{m.role === "user" ? "You" : "Agent"}</span>
          <div className="message-content">
            {m.role === "assistant" ? <Markdown content={m.content} /> : m.content}
          </div>
        </div>
      ))}
      {isStreaming && (
        <div className="message-streaming" role="status" aria-live="polite">
          <Spinner size="sm" label="Agent is working" />
          <span>Agent is working...</span>
        </div>
      )}
      {approvals.map((a) => (
        <ApprovalCard
          key={a.id}
          approval={a}
          onApprove={() => {
            api.approve(a.id).catch(() => {});
            resolveApproval(a.id);
          }}
          onDeny={() => {
            api.deny(a.id).catch(() => {});
            resolveApproval(a.id);
          }}
        />
      ))}
    </div>
  );
}
