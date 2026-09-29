// apps/vibe/src/App.tsx
import { SessionsPanel } from "./features/sessions/SessionsPanel";
import { ChatPanel } from "./features/chat/ChatPanel";
import { PreviewPanel } from "./features/preview/PreviewPanel";
import { CodePanel } from "./features/code/CodePanel";
import { SettingsPanel } from "./features/settings/SettingsPanel";
import { useSessionsStore } from "./features/sessions/store";

export default function App() {
  const activeId = useSessionsStore((s) => s.activeId);
  return (
    <div style={{ display: "flex", height: "100vh" }}>
      <SessionsPanel />
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {activeId ? <ChatPanel sessionId={activeId} /> : <div>Select a session</div>}
      </div>
      <div style={{ width: "40%", display: "flex", flexDirection: "column" }}>
        {activeId && <PreviewPanel sessionId={activeId} />}
        {activeId && <CodePanel files={[]} selectedFile={null} />}
      </div>
      <SettingsPanel />
    </div>
  );
}
