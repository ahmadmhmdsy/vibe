// apps/vibe/src/features/chat/ChatPanel.tsx — the conversation column.
// .panel arranges the column (see styles/layout.css); the header holds the
// session title and usage, the body holds the transcript and the composer
// (whose own toolbar carries the model picker).

import { MessageList } from "./MessageList";
import { Composer } from "./Composer";
import { UsageBadge } from "./UsageBadge";
import { useSessionsStore } from "../sessions/store";
import "./chat.css";

export function ChatPanel({ sessionId }: { sessionId: string }) {
  const title = useSessionsStore((s) => s.sessions.find((x) => x.id === s.activeId)?.title);

  return (
    <div className="panel chat-panel">
      <div className="panel-header">
        <h2 className="panel-title" title={title || undefined}>
          {title || "Chat"}
        </h2>
        <div className="panel-header-spacer" />
        <div className="panel-actions">
          {/* The model picker lives in the composer toolbar, one component,
              so the model is chosen where the message is written. */}
          <UsageBadge sessionId={sessionId} />
        </div>
      </div>
      <div className="panel-body" data-direction="column">
        <MessageList sessionId={sessionId} />
        <Composer sessionId={sessionId} />
      </div>
    </div>
  );
}
