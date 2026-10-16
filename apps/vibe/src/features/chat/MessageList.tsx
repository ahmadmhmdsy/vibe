// features/chat/MessageList.tsx — the conversation transcript.
//
// The transcript is a fold over the session's event log (see ../timeline): the
// SSE stream is cleared and the log replayed on open, then every published
// event — user and assistant messages, tool calls and results, errors, notices
// — is folded in. Nothing is filtered to a single type, which is what stops a
// long tool run from looking like a spinner with no explanation.

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Approval } from "../../lib/api";
import { SSEClient, type StreamStatus } from "../../lib/sse";
import { EMPTY_TIMELINE, useChatStore } from "./store";
import { Button } from "../../components/ui/Button";
import { ConnectionBanner } from "../../components/ui/ConnectionBanner";
import { EmptyState } from "../../components/ui/EmptyState";
import { Spinner } from "../../components/ui/Spinner";
import { Icon } from "../../components/icons/Icon";
import { ApprovalCard } from "./ApprovalCard";
import { TimelineItemView } from "./TimelineItemView";
import { usePolling } from "../../hooks/usePolling";
import "./chat.css";

/** Distance from the bottom within which the view counts as "following along". */
const PINNED_THRESHOLD_PX = 24;

export function MessageList({ sessionId }: { sessionId: string }) {
  const timeline = useChatStore((s) => s.timelineBySession[sessionId] ?? EMPTY_TIMELINE);
  const applyStreamEvent = useChatStore((s) => s.applyStreamEvent);
  const resetTimeline = useChatStore((s) => s.resetTimeline);
  const endStream = useChatStore((s) => s.endStream);
  const isStreaming = useChatStore((s) => s.isStreamingBySession[sessionId] ?? false);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [sseStatus, setSseStatus] = useState<StreamStatus>("idle");
  const [isPinned, setIsPinned] = useState(true);
  const [canScroll, setCanScroll] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const sseRef = useRef<SSEClient | null>(null);

  const items = timeline.items;

  // Poll for new approvals.
  usePolling(
    async () => {
      const data = await api.listApprovals(sessionId);
      setApprovals(data.filter((a) => a.status === "pending"));
    },
    { interval: 3000, enabled: true }
  );

  // Scrollability is measured, not assumed. A transcript that fits inside its
  // box is already at the bottom and will never fire a scroll event, so a
  // control gated on isPinned alone could sit on screen with nothing to jump to.
  const measure = useCallback(() => {
    const el = listRef.current;
    if (!el) return;
    const overflow = el.scrollHeight - el.clientHeight;
    setCanScroll(overflow > PINNED_THRESHOLD_PX);
    setIsPinned(overflow - el.scrollTop <= PINNED_THRESHOLD_PX);
  }, []);

  // Follow new items, a live chunk, or an approval — but only while the user is
  // already at the bottom. Assigning scrollTop unconditionally yanked the view
  // back down while someone was reading earlier messages.
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    if (isPinned) el.scrollTop = el.scrollHeight;
    measure();
  }, [items, isStreaming, approvals, isPinned, measure]);

  // A window or panel resize changes what fits without changing the transcript.
  useEffect(() => {
    const el = listRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => measure());
    observer.observe(el);
    measure();
    return () => observer.disconnect();
  }, [measure]);

  useEffect(() => {
    // No origin here on purpose: SSEClient defaults to the one API base in
    // lib/api.ts, so a VITE_API_URL change cannot leave the stream pointing
    // somewhere the REST client is not.
    const sse = new SSEClient();
    sseRef.current = sse;
    // The server replays the whole log from seq 0 on connect, so clear first:
    // a session switch must not blend the previous session's transcript in.
    resetTimeline(sessionId);
    sse.connect(
      sessionId,
      (e) => {
        applyStreamEvent(sessionId, e);
        // turn_complete/turn-aborted close the run. The composer's POST usually
        // resolves at the same moment, but a run stopped from another tab, or a
        // replayed log, has no local POST to fall back on.
        if (e.type === "turn_complete" || e.type === "turn/aborted") endStream(sessionId);
      },
      setSseStatus
    );
    return () => {
      sseRef.current = null;
      sse.disconnect();
    };
  }, [sessionId, resetTimeline, applyStreamEvent, endStream]);

  const jumpToLatest = () => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
    setIsPinned(true);
  };

  const resolveApproval = (id: string) => {
    setApprovals((prev) => prev.filter((x) => x.id !== id));
  };

  // While a tool is running or text is still arriving, the item itself is the
  // progress indicator; a second "working" line underneath would be noise.
  const hasLiveItem = items.some(
    (item) =>
      (item.kind === "tool" && item.status === "running") ||
      (item.kind === "assistant" && item.streaming)
  );
  const showWorking = isStreaming && !hasLiveItem;

  return (
    <div className="message-list scroll-region" ref={listRef} onScroll={measure}>
      <ConnectionBanner status={sseStatus} onRetry={() => sseRef.current?.retry()} />

      {/* role="log" is itself a polite live region. The connection alert above is
          a sibling of it, not a child, so it is not announced twice. */}
      <div
        className="message-log"
        role="log"
        aria-live="polite"
        aria-label="Conversation transcript"
      >
        {items.length === 0 && !isStreaming && (
          <EmptyState
            icon={<Icon name="chat" size={24} />}
            title="Describe the app you want to build"
            body="The agent writes the files, installs dependencies, and runs the preview. Every step it takes shows up here."
          />
        )}

        {items.map((item) => (
          <TimelineItemView key={item.id} item={item} />
        ))}

        {showWorking && (
          // A plain element: the transcript is already the live region, and a
          // status region nested inside it announces the same event twice.
          <div className="message-streaming">
            <Spinner size="sm" label="Agent is working" live={false} />
            <span>Agent is working…</span>
          </div>
        )}

        {approvals.map((a) => (
          <ApprovalCard
            key={a.id}
            approval={a}
            onApprove={async () => {
              await api.approve(a.id);
              resolveApproval(a.id);
            }}
            onDeny={async () => {
              await api.deny(a.id);
              resolveApproval(a.id);
            }}
          />
        ))}
      </div>

      {canScroll && !isPinned && (
        <div className="message-jump">
          <Button variant="ghost" size="sm" onClick={jumpToLatest}>
            Jump to latest
          </Button>
        </div>
      )}
    </div>
  );
}
