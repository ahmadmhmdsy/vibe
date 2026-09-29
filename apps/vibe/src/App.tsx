// apps/vibe/src/App.tsx
import { useState } from "react";
import { SessionsPanel } from "./features/sessions/SessionsPanel";
import { ChatPanel } from "./features/chat/ChatPanel";
import { PreviewPanel } from "./features/preview/PreviewPanel";
import { CodePanel } from "./features/code/CodePanel";
import { SettingsPanel } from "./features/settings/SettingsPanel";
import { Modal } from "./components/ui/Modal";
import { IconButton } from "./components/ui/IconButton";
import { EmptyState } from "./components/ui/EmptyState";
import { Button } from "./components/ui/Button";
import { useSessionsStore } from "./features/sessions/store";
import { useKeyboardShortcut } from "./hooks/useKeyboardShortcut";
import "./styles/app.css";

type MobileTab = "chat" | "code" | "preview";

export default function App() {
  const activeId = useSessionsStore((s) => s.activeId);
  const activeSession = useSessionsStore((s) => s.sessions.find((x) => x.id === s.activeId));
  const create = useSessionsStore((s) => s.create);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const [sideOpen, setSideOpen] = useState(false);
  const [mobileTab, setMobileTab] = useState<MobileTab>("chat");

  useKeyboardShortcut(() => setSettingsOpen((v) => !v), { meta: true, key: "," });

  return (
    <div className="app-shell">
      <header className="app-header">
        <IconButton
          label="Sessions"
          className="app-header-sessions-toggle"
          onClick={() => setSessionsOpen((v) => !v)}
        >
          <svg width="18" height="18" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <rect x="1.5" y="1.5" width="13" height="13" rx="2" />
            <path d="M1.5 5.5h13M5.5 5.5v9" />
          </svg>
        </IconButton>
        <h1 className="app-brand">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M3 10l4-4 4 4 4-4 2 2" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M3 15l4-4 4 4 4-4 2 2" stroke="var(--text-faint)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span>vibe</span>
        </h1>
        <div className="app-header-title" title={activeSession?.title}>
          {activeSession ? activeSession.title : "local vibe-coding IDE"}
        </div>
        <IconButton
          label="Preview and code"
          className="app-header-side-toggle"
          onClick={() => setSideOpen((v) => !v)}
        >
          <svg width="18" height="18" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <rect x="1.5" y="1.5" width="13" height="13" rx="2" />
            <path d="M9.5 1.5v13" />
          </svg>
        </IconButton>
        <IconButton label="Settings" onClick={() => setSettingsOpen(true)}>
          <svg width="18" height="18" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <circle cx="8" cy="8" r="2.2" />
            <path d="M8 1.8v1.7M8 12.5v1.7M1.8 8h1.7M12.5 8h1.7M3.6 3.6l1.2 1.2M11.2 11.2l1.2 1.2M12.4 3.6l-1.2 1.2M4.8 11.2l-1.2 1.2" strokeLinecap="round" />
          </svg>
        </IconButton>
      </header>

      <div className="app-body">
        <aside className={["app-sidebar", sessionsOpen ? "app-sidebar-open" : ""].join(" ")}>
          <SessionsPanel />
        </aside>

        <main className="app-main" data-mobile-tab={mobileTab}>
          {activeId ? (
            <ChatPanel sessionId={activeId} />
          ) : (
            <EmptyState
              title="No session selected"
              body="Start a new session and describe the app you want to build — the agent handles the rest."
              action={
                <Button variant="primary" onClick={() => create()}>
                  New session
                </Button>
              }
            />
          )}
        </main>

        <section className={["app-side", sideOpen ? "app-side-open" : ""].join(" ")}>
          {activeId && <PreviewPanel sessionId={activeId} />}
          {activeId && <CodePanel sessionId={activeId} />}
        </section>
      </div>

      <nav className="app-mobile-tabs" aria-label="Panels">
        {(["chat", "code", "preview"] as MobileTab[]).map((tab) => (
          <button
            key={tab}
            className={mobileTab === tab ? "app-mobile-tab active" : "app-mobile-tab"}
            aria-pressed={mobileTab === tab}
            onClick={() => setMobileTab(tab)}
          >
            {tab === "chat" ? "Chat" : tab === "code" ? "Code" : "Preview"}
          </button>
        ))}
      </nav>

      <Modal open={settingsOpen} onClose={() => setSettingsOpen(false)} title="Settings" wide>
        <SettingsPanel />
      </Modal>
    </div>
  );
}
