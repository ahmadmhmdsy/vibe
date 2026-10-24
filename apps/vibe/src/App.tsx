// App.tsx — the composition layer.
//
// The shell owns layout, panel visibility, and the keyboard map. Feature
// modules own their own state and never reach into each other; the thing that
// decides whether Preview or Code is on screen lives here, in app/, precisely
// so the chat feature never has to import the preview feature.

import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { AppHeader } from "./app/AppHeader";
import { SidePanelHost, type SideTab } from "./app/SidePanelHost";
import { SessionsPanel } from "./features/sessions/SessionsPanel";
import { ChatPanel } from "./features/chat/ChatPanel";
import { SettingsPanel } from "./features/settings/SettingsPanel";
import { Button } from "./components/ui/Button";
import { CommandPalette } from "./components/ui/CommandPalette";
import { EmptyState } from "./components/ui/EmptyState";
import { Icon } from "./components/icons/Icon";
import { Modal } from "./components/ui/Modal";
import { ShortcutsHelp } from "./components/ui/ShortcutsHelp";
import { Splitter } from "./components/ui/Splitter";
import { useSessionsStore } from "./features/sessions/store";
import { useChatStore } from "./features/chat/store";
import { useSettingsStore } from "./features/settings/store";
import { FirstRun } from "./features/onboarding/FirstRun";
import { shouldShowFirstRun, useFirstRunStore } from "./features/onboarding/store";
import { useElementWidth } from "./hooks/useElementWidth";
import { useKeyboardShortcut } from "./hooks/useKeyboardShortcut";
import { useIsDesktop, useIsMobile } from "./hooks/useMediaQuery";
// Aliased: the state setter below is also named setTheme, and the collision
// silently made the apply-on-mount effect a no-op.
import { getTheme, setTheme as applyTheme, toggleTheme, type Theme } from "./lib/theme";
import { isMacPlatform } from "./lib/platform";
import "./app/shell.css";

type MobileTab = "chat" | SideTab;

/** Limits for the right-hand column, matching --side-width-min / --max in
 *  tokens.css. Below --side-width-min the preview iframe is useless; above the
 *  max the conversation stops being the widest column. */
const SIDE_MIN = 320;
const SIDE_MAX = 560;
const defaultSideWidth = () =>
  Math.round(Math.min(SIDE_MAX, Math.max(SIDE_MIN, window.innerWidth * 0.34)));

export default function App() {
  const activeId = useSessionsStore((s) => s.activeId);
  const activeSession = useSessionsStore((s) => s.sessions.find((x) => x.id === s.activeId));
  const create = useSessionsStore((s) => s.create);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  // Set when the first-run panel sent the user to Settings, so the provider
  // form gets the focus instead of the dialog's first tabbable element.
  const [focusProviders, setFocusProviders] = useState(false);

  // Two pairs of flags, because a column means something different either side
  // of the breakpoints: collapsed is a desktop grid track, open is a drawer.
  // They are flipped together so one control drives both.
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarDrawerOpen, setSidebarDrawerOpen] = useState(false);
  const [sideCollapsed, setSideCollapsed] = useState(false);
  const [sideDrawerOpen, setSideDrawerOpen] = useState(false);

  const [sideTab, setSideTab] = useState<SideTab>("preview");
  const [mobileTab, setMobileTab] = useState<MobileTab>("chat");
  // null means "whatever the CSS clamp says"; a number is a width the user chose.
  const [sideWidth, setSideWidth] = useState<number | null>(null);

  const [theme, setTheme] = useState<Theme>(getTheme);
  const isMac = isMacPlatform();
  const isMobile = useIsMobile();
  const isDesktop = useIsDesktop();

  const { ref: sideRef, width: measuredSideWidth } = useElementWidth<HTMLElement>();

  useKeyboardShortcut(() => setSettingsOpen((v) => !v), { meta: true, key: "," });
  useKeyboardShortcut(() => setPaletteOpen((v) => !v), { meta: true, key: "k" });
  useKeyboardShortcut(() => setShortcutsOpen((v) => !v), { key: "?" });

  // New session is advertised in the palette, so the binding has to exist on
  // every platform. Ctrl+N and Ctrl+Shift+N are browser-reserved on
  // Windows/Linux, so those platforms get Ctrl+Alt+N instead.
  useKeyboardShortcut(
    () => create(),
    isMac ? { meta: true, key: "n" } : { ctrl: true, alt: true, key: "n" }
  );

  // Apply the persisted theme on first paint. It was only ever written by an
  // explicit toggle, so a reload lost the user's choice for that render.
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // The window title is the only place a user can tell two sessions apart in
  // the OS task switcher.
  useEffect(() => {
    document.title = activeSession
      ? `${activeSession.title} — vibe`
      : "vibe — local vibe-coding IDE";
  }, [activeSession]);

  // Is this install able to talk to a model at all? Asked once at start-up, and
  // again whenever Settings changes the provider list, so adding a key makes the
  // guidance below disappear without a reload.
  const firstRunProviders = useFirstRunStore((s) => s.providers);
  const firstRunLoaded = useFirstRunStore((s) => s.loaded);
  const refreshFirstRun = useFirstRunStore((s) => s.refresh);
  const settingsProviders = useSettingsStore((s) => s.providers);
  useEffect(() => {
    void refreshFirstRun();
  }, [refreshFirstRun, settingsProviders]);
  const showFirstRun = shouldShowFirstRun(firstRunProviders, firstRunLoaded);

  // An example prompt fills the composer rather than sending: the user still
  // decides when to spend a model call. create() returns the new id, so the
  // draft is keyed to the session that is about to mount.
  const useExample = useCallback(
    async (prompt: string) => {
      const sid = await create();
      useChatStore.getState().setPendingDraft(sid, prompt);
    },
    [create]
  );

  const closeDrawers = useCallback(() => {
    setSidebarDrawerOpen(false);
    setSideDrawerOpen(false);
  }, []);

  // Escape always dismisses an open drawer, even from inside the composer.
  useKeyboardShortcut(closeDrawers, { key: "Escape", allowInInput: true });

  const onToggleTheme = () => setTheme(toggleTheme());

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((v) => !v);
    setSidebarDrawerOpen((v) => !v);
  }, []);

  const toggleSide = useCallback(() => {
    setSideCollapsed((v) => !v);
    setSideDrawerOpen((v) => !v);
  }, []);

  // Declared after the handlers above because the hook is called during render
  // and would hit the temporal dead zone if it preceded them. Cmd/Ctrl+B is the
  // sidebar convention; Cmd/Ctrl+J mirrors it for the preview and code column.
  // Both must also fire from inside the composer, or the shortcut is useless
  // exactly when the user wants to glance at the preview.
  useKeyboardShortcut(toggleSidebar, { meta: true, key: "b", allowInInput: true });
  useKeyboardShortcut(toggleSide, { meta: true, key: "j", allowInInput: true });

  const changeSideTab = useCallback(
    (tab: SideTab) => {
      setSideTab(tab);
      if (isMobile) setMobileTab(tab);
    },
    [isMobile]
  );

  const selectMobileTab = useCallback((tab: MobileTab) => {
    setMobileTab(tab);
    if (tab !== "chat") setSideTab(tab);
    setSidebarDrawerOpen(false);
    setSideDrawerOpen(false);
  }, []);

  const commands = [
    {
      id: "new-session",
      title: "New session",
      description: "Create a new chat session",
      action: () => create(),
      shortcut: isMac ? ["Cmd", "N"] : ["Ctrl", "Alt", "N"],
    },
    {
      id: "toggle-side",
      title: sideCollapsed ? "Show preview and code" : "Hide preview and code",
      description: "Toggle the right-hand panel",
      action: toggleSide,
    },
    {
      id: "toggle-sidebar",
      title: sidebarCollapsed ? "Show sessions" : "Hide sessions",
      description: "Toggle the sessions sidebar",
      action: toggleSidebar,
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
      // The binding works with Ctrl on Windows/Linux (meta accepts either), so
      // the label must not claim a Cmd key those keyboards do not have.
      shortcut: isMac ? ["Cmd", ","] : ["Ctrl", ","],
    },
    {
      id: "show-shortcuts",
      title: "Show keyboard shortcuts",
      description: "View all available shortcuts",
      action: () => setShortcutsOpen(true),
      shortcut: ["?"],
    },
  ];

  const drawerOpen = sidebarDrawerOpen || sideDrawerOpen;
  const title = activeSession ? activeSession.title : "local vibe-coding IDE";

  return (
    <div className="app-shell">
      <AppHeader
        title={title}
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebar={toggleSidebar}
        sideCollapsed={sideCollapsed}
        onToggleSide={toggleSide}
        onOpenPalette={() => setPaletteOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
        theme={theme}
        onToggleTheme={onToggleTheme}
        isMac={isMac}
      />

      <div
        className="app-body"
        data-sidebar={sidebarCollapsed ? "collapsed" : undefined}
        data-side={sideCollapsed ? "collapsed" : undefined}
        data-mobile-tab={mobileTab}
        style={
          sideWidth === null ? undefined : ({ "--side-width": `${sideWidth}px` } as CSSProperties)
        }
      >
        <aside
          className={["app-sidebar", sidebarDrawerOpen ? "app-sidebar-open" : ""]
            .filter(Boolean)
            .join(" ")}
          aria-label="Sessions"
        >
          <SessionsPanel />
        </aside>

        <main className="app-main" aria-label="Conversation">
          {activeId ? (
            <ChatPanel sessionId={activeId} />
          ) : showFirstRun ? (
            <FirstRun
              onOpenSettings={() => {
                setFocusProviders(true);
                setSettingsOpen(true);
              }}
              onUseExample={useExample}
            />
          ) : (
            <EmptyState
              icon={<Icon name="message" size={28} />}
              title="No session selected"
              body="Start a session and describe the app you want to build — the agent handles the rest."
              action={
                <Button variant="primary" onClick={() => create()}>
                  New session
                </Button>
              }
            />
          )}
        </main>

        <SidePanelHost
          ref={sideRef}
          sessionId={activeId}
          theme={theme}
          tab={sideTab}
          onTabChange={changeSideTab}
          open={sideDrawerOpen}
          leading={
            activeId ? (
              <Splitter
                value={sideWidth ?? measuredSideWidth}
                min={SIDE_MIN}
                max={SIDE_MAX}
                defaultValue={defaultSideWidth()}
                invert
                label="Resize the preview and code panel"
                onChange={setSideWidth}
              />
            ) : null
          }
        />
      </div>

      {drawerOpen && !isDesktop ? (
        <button type="button" className="scrim" aria-label="Close panel" onClick={closeDrawers} />
      ) : null}

      <nav className="app-mobile-tabs" aria-label="Panels">
        {(
          [
            { id: "chat", label: "Chat", icon: "chat" },
            { id: "code", label: "Code", icon: "code" },
            { id: "preview", label: "Preview", icon: "play" },
            { id: "vcs", label: "Source", icon: "branch" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={mobileTab === tab.id ? "app-mobile-tab active" : "app-mobile-tab"}
            aria-pressed={mobileTab === tab.id}
            onClick={() => selectMobileTab(tab.id)}
          >
            <Icon name={tab.icon} size={16} />
            <span>{tab.label}</span>
          </button>
        ))}
      </nav>

      <Modal
        open={settingsOpen}
        onClose={() => {
          setSettingsOpen(false);
          setFocusProviders(false);
        }}
        title="Settings"
        wide
      >
        <SettingsPanel focusProviders={focusProviders} />
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
