// apps/vibe/src/features/chat/ChatPanel.tsx
import { MessageList } from "./MessageList";
import { Composer } from "./Composer";
import { ModelPicker } from "./ModelPicker";

export function ChatPanel({ sessionId }: { sessionId: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <ModelPicker />
      <MessageList sessionId={sessionId} />
      <Composer sessionId={sessionId} />
    </div>
  );
}
