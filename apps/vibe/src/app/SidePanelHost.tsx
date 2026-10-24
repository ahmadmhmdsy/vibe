// app/SidePanelHost.tsx — the side tab host: preview, code, source control.
//
// This lives in the composition layer on purpose: the chat feature must never
// import the preview feature, so the thing that decides which of them is on
// screen belongs to the shell. Every panel is lazily loaded and stays mounted
// once opened, so switching tabs never tears down the preview iframe.

import { forwardRef, lazy, Suspense, type ReactNode } from "react";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorBoundary } from "../components/ui/ErrorBoundary";
import { Icon } from "../components/icons/Icon";
import { Loading } from "../components/ui/Loading";
import { TabPanel, Tabs, type TabItem } from "../components/ui/Tabs";
import type { Theme } from "../lib/theme";

const PreviewPanel = lazy(() =>
  import("../features/preview/PreviewPanel").then((m) => ({ default: m.PreviewPanel }))
);
const CodePanel = lazy(() =>
  import("../features/code/CodePanel").then((m) => ({ default: m.CodePanel }))
);
const SourceControlPanel = lazy(() =>
  import("../features/vcs/SourceControlPanel").then((m) => ({
    default: m.SourceControlPanel,
  }))
);

export type SideTab = "preview" | "code" | "vcs";

const TABS: readonly TabItem[] = [
  { id: "preview", label: "Preview", icon: <Icon name="play" size={14} /> },
  { id: "code", label: "Code", icon: <Icon name="code" size={14} /> },
  { id: "vcs", label: "Source", icon: <Icon name="branch" size={14} /> },
];

export interface SidePanelHostProps {
  sessionId: string | null;
  theme: Theme;
  tab: SideTab;
  onTabChange: (tab: SideTab) => void;
  /** Drawer state for tablet and mobile widths. */
  open: boolean;
  /** Rendered inside the section, before the tabs. The shell passes the
   *  resize handle here so it belongs to the landmark it resizes. */
  leading?: ReactNode;
}

/** The ref is forwarded so the shell can measure the column and hand the
 *  splitter a real width to report. */
export const SidePanelHost = forwardRef<HTMLElement, SidePanelHostProps>(function SidePanelHost(
  { sessionId, theme, tab, onTabChange, open, leading },
  ref
) {
  return (
    <section
      ref={ref}
      className={["app-side", open ? "app-side-open" : ""].filter(Boolean).join(" ")}
      aria-label="Preview, code, and source control"
    >
      {leading}

      <div className="app-side-tabs">
        <Tabs
          items={TABS}
          value={tab}
          onChange={(id) => onTabChange(id as SideTab)}
          label="Right panel"
          variant="underline"
          idPrefix="side"
        />
      </div>

      {sessionId ? (
        <div className="app-side-content">
          <TabPanel id="preview" idPrefix="side" active={tab === "preview"}>
            <ErrorBoundary resetKey={sessionId}>
              <Suspense fallback={<Loading label="Loading preview" />}>
                <PreviewPanel sessionId={sessionId} active={tab === "preview"} />
              </Suspense>
            </ErrorBoundary>
          </TabPanel>

          <TabPanel id="code" idPrefix="side" active={tab === "code"}>
            <ErrorBoundary resetKey={sessionId}>
              <Suspense fallback={<Loading label="Loading code" />}>
                <CodePanel sessionId={sessionId} theme={theme} active={tab === "code"} />
              </Suspense>
            </ErrorBoundary>
          </TabPanel>

          <TabPanel id="vcs" idPrefix="side" active={tab === "vcs"}>
            <ErrorBoundary resetKey={sessionId}>
              <Suspense fallback={<Loading label="Loading source control" />}>
                <SourceControlPanel sessionId={sessionId} active={tab === "vcs"} />
              </Suspense>
            </ErrorBoundary>
          </TabPanel>
        </div>
      ) : (
        <EmptyState
          icon={<Icon name="code" size={28} />}
          title="Nothing to show yet"
          body="Start a session. Once the agent writes files, the app it builds appears here."
        />
      )}
    </section>
  );
});
