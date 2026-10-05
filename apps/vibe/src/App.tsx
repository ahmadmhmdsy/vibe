// apps/vibe/src/App.tsx — Application shell.
// 3-column layout: sessions sidebar, chat, preview/code side panel.

import { useState, useCallback, lazy, Suspense } from "react";
import { SessionsPanel } from "./features/sessions/SessionsPanel";
import { ChatPanel } from "./features/chat/ChatPanel";
import { SettingsPanel } from "./features/settings/SettingsPanel";
import { Modal } from "./components/ui/Modal";
import { IconButton } from "./components/ui/IconButton";
import { EmptyState } from "./components/ui/EmptyState";
import { Button } from "./components/ui/Button";
import { ShortcutsHelp } from "./components/ui/ShortcutsHelp";
import { CommandPalette } from "./components/ui/CommandPalette";
import { Loading } from "./components/ui/Loading";
import { ErrorBoundary } from "./components/ui/ErrorBoundary";
import { useSessionsStore } from "./features/sessions/store";
import { useKeyboardShortcut } from "./hooks/useKeyboardShortcut";
import { useIsMobile } from "./hooks/useMediaQuery";
import { getTheme, toggleTheme, type Theme } from "./lib/theme";
import "./styles/app.css";

// Lazy load heavy panels
const PreviewPanel = lazy(() =>
  import("./features/preview/PreviewPanel").then((m) => ({ default: m.PreviewPanel }))
);
const CodePanel = lazy(() =>
  import("./features/code/CodePanel").then((m) => ({ default: m.CodePanel }))
);

type MobileTab = "chat" | "code" | "preview";

export default function App() {
  const activeId = useSessionsStore((s) => s.activeId);
  const activeSession = useSessionsStore((s) => s.sessions.find((x) => x.id === s.activeId));
  const create = useSessionsStore((s) => s.create);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const [sideOpen, setSideOpen] = useState(false);
  const [mobileTab, setMobileTab] = useState<MobileTab>("chat");
  const [theme, setTheme] = useState<Theme>(getTheme);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useKeyboardShortcut(() => setSettingsOpen((v) => !v), { meta: true, key: "," });
  useKeyboardShortcut(() => setPaletteOpen((v) => !v), { meta: true, key: "k" });
  useKeyboardShortcut(() => setShortcutsOpen((v) => !v), { key: "?" });

  // On mobile the side column replaces the chat column, so it has to carry
  // the document's single main landmark while it owns the viewport.
  const isMobile = useIsMobile();
  const sideIsMain = isMobile && mobileTab !== "chat";

  const closeDrawers = useCallback(() => {
    setSessionsOpen(false);
    setSideOpen(false);
  }, []);

  // Escape always dismisses an open drawer, even from inside the composer.
  useKeyboardShortcut(closeDrawers, { key: "Escape", allowInInput: true });

  const onToggleTheme = () => setTheme(toggleTheme());

  const selectMobileTab = (tab: MobileTab) => {
    setMobileTab(tab);
    closeDrawers();
  };

  const commands = [
    {
      id: "new-session",
      title: "New session",
      description: "Create a new chat session",
      action: () => create(),
      shortcut: ["Cmd", "N"],
    },
    {
      id: "toggle-theme",
      title: "Toggle theme",
      description: "Switch between dark and light mode",
      action: onToggleTheme,
    },
    {
      id: "open-settings",
      title: "Open settings",
      description: "Configure providers and API keys",
      action: () => setSettingsOpen(true),
      shortcut: ["Cmd", ","],
    },
    {
      id: "show-shortcuts",
      title: "Show keyboard shortcuts",
      description: "View all available shortcuts",
      action: () => setShortcutsOpen(true),
      shortcut: ["?"],
    },
  ];

  return (
    <div className="app-shell">
      <header className="app-header">
        <IconButton
          label="Sessions"
          className="app-header-sessions-toggle"
          onClick={() => setSessionsOpen((v) => !v)}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden="true"
          >
            <rect x="1.5" y="1.5" width="13" height="13" rx="2" />
            <path d="M1.5 5.5h13M5.5 5.5v9" />
          </svg>
        </IconButton>
        <h1 className="app-brand">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path
              d="M3 10l4-4 4 4 4-4 2 2"
              stroke="var(--accent)"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M3 15l4-4 4 4 4-4 2 2"
              stroke="var(--text-faint)"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
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
          <svg
            width="18"
            height="18"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden="true"
          >
            <rect x="1.5" y="1.5" width="13" height="13" rx="2" />
            <path d="M9.5 1.5v13" />
          </svg>
        </IconButton>
        <IconButton label="Toggle theme" onClick={onToggleTheme}>
          <svg
            width="18"
            height="18"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden="true"
          >
            {theme === "dark" ? (
              <>
                <circle cx="8" cy="8" r="3" />
                <path
                  d="M8 1.8v1.4M8 12.8v1.4M1.8 8h1.4M12.8 8h1.4M3.5 3.5l1 1M11.5 11.5l1 1M12.5 3.5l-1 1M4.5 11.5l-1 1"
                  strokeLinecap="round"
                />
              </>
            ) : (
              <path d="M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7z" strokeLinejoin="round" />
            )}
          </svg>
        </IconButton>
        <IconButton label="Settings" onClick={() => setSettingsOpen(true)}>
          <svg
            width="18"
            height="18"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden="true"
          >
            <circle cx="8" cy="8" r="2.2" />
            <path
              d="M8 1.8v1.7M8 12.5v1.7M1.8 8h1.7M12.5 8h1.7M3.6 3.6l1.2 1.2M11.2 11.2l1.2 1.2M12.4 3.6l-1.2 1.2M4.8 11.2l-1.2 1.2"
              strokeLinecap="round"
            />
          </svg>
        </IconButton>
      </header>

      <div className="app-body" data-mobile-tab={mobileTab}>
        <aside className={["app-sidebar", sessionsOpen ? "app-sidebar-open" : ""].join(" ")}>
          <SessionsPanel />
        </aside>

        <main className="app-main">
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

        <section
          className={["app-side", sideOpen ? "app-side-open" : ""].join(" ")}
          aria-label="Preview and code"
          role={sideIsMain ? "main" : undefined}
        >
          {activeId && (
            <ErrorBoundary resetKey={activeId}>
              <Suspense fallback={<Loading label="Loading preview" />}>
                <PreviewPanel sessionId={activeId} />
              </Suspense>
            </ErrorBoundary>
          )}
          {activeId && (
            <ErrorBoundary resetKey={activeId}>
              <Suspense fallback={<Loading label="Loading code" />}>
                <CodePanel sessionId={activeId} />
              </Suspense>
            </ErrorBoundary>
          )}
        </section>
      </div>

      <nav className="app-mobile-tabs" aria-label="Panels">
        {(["chat", "code", "preview"] as MobileTab[]).map((tab) => (
          <button
            key={tab}
            className={mobileTab === tab ? "app-mobile-tab active" : "app-mobile-tab"}
            aria-pressed={mobileTab === tab}
            onClick={() => selectMobileTab(tab)}
          >
            {tab === "chat" ? "Chat" : tab === "code" ? "Code" : "Preview"}
          </button>
        ))}
      </nav>

      <Modal open={settingsOpen} onClose={() => setSettingsOpen(false)} title="Settings" wide>
        <SettingsPanel />
      </Modal>

      <ShortcutsHelp open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        commands={commands}
      />
    </div>
  );
}
