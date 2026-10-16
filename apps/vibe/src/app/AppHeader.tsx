// app/AppHeader.tsx — the application bar.
//
// The header carries identity and global actions only. Which right-hand panel
// is showing belongs next to that panel (see SidePanelHost), not up here.

import { Icon } from "../components/icons/Icon";
import { IconButton } from "../components/ui/IconButton";
import { Kbd } from "../components/ui/Kbd";
import type { Theme } from "../lib/theme";

export interface AppHeaderProps {
  /** The current session's title, or the product's own line when none is open. */
  title: string;
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  sideCollapsed: boolean;
  onToggleSide: () => void;
  onOpenPalette: () => void;
  onOpenSettings: () => void;
  theme: Theme;
  onToggleTheme: () => void;
  isMac: boolean;
}

/** The product mark. Hand-drawn rather than an icon-font glyph: it is the one
 *  place the interface is allowed to be decorative. */
function BrandMark() {
  return (
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
  );
}

export function AppHeader({
  title,
  sidebarCollapsed,
  onToggleSidebar,
  sideCollapsed,
  onToggleSide,
  onOpenPalette,
  onOpenSettings,
  theme,
  onToggleTheme,
  isMac,
}: AppHeaderProps) {
  return (
    <header className="app-header">
      <IconButton
        label={sidebarCollapsed ? "Show sessions" : "Hide sessions"}
        className="app-header-sidebar-toggle"
        tooltipSide="bottom"
        aria-expanded={!sidebarCollapsed}
        onClick={onToggleSidebar}
      >
        <Icon name="panelLeft" size={18} />
      </IconButton>

      <div className="app-brand">
        <BrandMark />
        <span>vibe</span>
      </div>

      <span className="app-header-divider" aria-hidden="true" />

      {/* The session is the page's subject, so it is the page's only h1. */}
      <h1 className="app-header-title" title={title}>
        {title}
      </h1>

      <div className="app-header-spacer" />

      {/* The label collapses to a bare icon under 900px, so the accessible
          name must not depend on the visible text. */}
      <button
        type="button"
        className="app-header-search"
        aria-label="Search or run a command"
        onClick={onOpenPalette}
      >
        <Icon name="search" size={14} />
        <span className="app-header-search-label">Search or run a command</span>
        <Kbd keys={isMac ? ["Cmd", "K"] : ["Ctrl", "K"]} />
      </button>

      <IconButton
        label={sideCollapsed ? "Show preview and code" : "Hide preview and code"}
        className="app-header-side-toggle"
        tooltipSide="bottom"
        aria-expanded={!sideCollapsed}
        onClick={onToggleSide}
      >
        <Icon name="panelRight" size={18} />
      </IconButton>

      <IconButton
        label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
        tooltipSide="bottom"
        onClick={onToggleTheme}
      >
        <Icon name={theme === "dark" ? "themeLight" : "themeDark"} size={18} />
      </IconButton>

      <IconButton label="Settings" tooltipSide="bottom" onClick={onOpenSettings}>
        <Icon name="settings" size={18} />
      </IconButton>
    </header>
  );
}
