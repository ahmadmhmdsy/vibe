// apps/vibe/src/features/chat/ChatPanel.tsx
import { MessageList } from "./MessageList";
import { Composer } from "./Composer";
import { ModelPicker } from "./ModelPicker";
import { UsageBadge } from "./UsageBadge";
import "./chat.css";

export function ChatPanel({ sessionId }: { sessionId: string }) {
  return (
    <div className="chat-panel">
      <ModelPicker sessionId={sessionId} />
      <MessageList sessionId={sessionId} />
      <UsageBadge sessionId={sessionId} />
      <Composer sessionId={sessionId} />
    </div>
  );
}
