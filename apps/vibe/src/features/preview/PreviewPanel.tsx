// features/preview/PreviewPanel.tsx — Live preview of the generated app.
// Polls the backend for dev-server status and displays the app in an iframe.

import { useCallback, useState } from "react";
import { EMPTY_PREVIEW, usePreviewStore } from "./store";
import {
  Badge,
  Button,
  EmptyState,
  ErrorBanner,
  IconButton,
  StatusDot,
  useToast,
  type BadgeTone,
  type StatusKind,
} from "../../components/ui";
import { Icon } from "../../components/icons/Icon";
import { usePolling } from "../../hooks/usePolling";
import "./preview.css";

type RunStatus = "stopped" | "running" | "error";

/** One chip answers "what is the dev server doing" in words, so the colour of
 *  the dot is never the only carrier of the state. */
const RUN_CHIP: Record<RunStatus, { tone: BadgeTone; status: StatusKind; label: string }> = {
  stopped: { tone: "neutral", status: "idle", label: "Stopped" },
  running: { tone: "success", status: "ok", label: "Running" },
  error: { tone: "danger", status: "error", label: "Error" },
};

export function PreviewPanel({
  sessionId,
  /**
   * Whether the panel is the visible one. The 2s status poll runs only while
   * active so a hidden Preview tab costs no requests. Optional and defaulting
   * to true so the existing call site keeps its behaviour.
   */
  active = true,
}: {
  sessionId: string;
  active?: boolean;
}) {
  // Per-session state: a single global url/status showed one session's preview
  // after switching to another.
  const { url, isRunning, loading, error } = usePreviewStore(
    (s) => s.bySession[sessionId] ?? EMPTY_PREVIEW
  );
  const run = usePreviewStore((s) => s.run);
  const stop = usePreviewStore((s) => s.stop);
  const { toast } = useToast();
  // Cache-busts the src on Reload. Mutating the iframe in place would need a
  // DOM write, which React would not know about; keying the src is declarative.
  const [reloadToken, setReloadToken] = useState(0);

  // Poll the backend for dev-server status while the tab is shown.
  usePolling(
    async () => {
      await usePreviewStore.getState().poll(sessionId);
    },
    { interval: 2000, enabled: active }
  );

  const copyUrl = useCallback(async () => {
    if (!url) return;
    try {
      // Absent on http origins in some browsers, so a failure is reported
      // rather than thrown.
      if (!navigator.clipboard) throw new Error("Clipboard is unavailable");
      await navigator.clipboard.writeText(url);
      toast("Preview URL copied", "success");
    } catch {
      toast("Could not copy the preview URL", "error");
    }
  }, [url, toast]);

  // Precedence: a live URL keeps the frame; without one, an error explains
  // itself; otherwise the panel is simply stopped.
  const state: RunStatus = error && !url ? "error" : isRunning && url ? "running" : "stopped";
  const chip = RUN_CHIP[state];
  const src = url ? (reloadToken ? `${url}?vibe-reload=${reloadToken}` : url) : null;

  return (
    <div className="panel panel-preview preview-panel">
      <div className="panel-header">
        {/* Identity, not a title: the shell's tab strip already says
            "Preview". Empty until a dev server has handed back a URL. */}
        {url && (
          <>
            <span className="preview-url" title={url}>
              {url.replace(/^https?:\/\//, "")}
            </span>
            <IconButton label="Copy preview URL" tooltipSide="bottom" onClick={copyUrl}>
              <Icon name="copy" size={14} />
            </IconButton>
          </>
        )}
        <div className="panel-header-spacer" />
        <Badge tone={chip.tone}>
          <StatusDot status={chip.status} label={chip.label} />
          {chip.label}
        </Badge>
        <div className="panel-actions">
          {isRunning ? (
            <Button variant="secondary" size="sm" onClick={() => stop(sessionId)}>
              Stop
            </Button>
          ) : (
            <Button
              variant="primary"
              size="sm"
              onClick={() => run(sessionId)}
              disabled={loading}
              loading={loading}
            >
              Run
            </Button>
          )}
          <IconButton
            label="Reload preview"
            tooltipSide="bottom"
            disabled={!url}
            onClick={() => setReloadToken((token) => token + 1)}
          >
            <Icon name="retry" size={14} />
          </IconButton>
          <IconButton
            label="Open preview in a new tab"
            tooltipSide="bottom"
            disabled={!url}
            onClick={() => {
              if (url) window.open(url, "_blank", "noopener");
            }}
          >
            <Icon name="external" size={14} />
          </IconButton>
        </div>
      </div>

      <div className="panel-body" data-direction="column" data-testid="preview-layout">
        {src ? (
          <iframe
            key={src}
            src={src}
            title="App preview"
            className="preview-frame"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
          />
        ) : state === "error" ? (
          <div className="preview-state">
            <ErrorBanner message={error ?? "Preview failed."} onRetry={() => run(sessionId)} />
          </div>
        ) : (
          <EmptyState
            icon={<Icon name="play" size={24} />}
            title="Preview is not running"
            body="Start the dev server to see the generated app here."
            action={
              <Button
                variant="primary"
                size="sm"
                onClick={() => run(sessionId)}
                disabled={loading}
                loading={loading}
              >
                Run preview
              </Button>
            }
          />
        )}
      </div>
    </div>
  );
}
