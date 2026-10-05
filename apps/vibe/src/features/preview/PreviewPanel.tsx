// features/preview/PreviewPanel.tsx — Live preview of the generated app.
// Polls the backend for dev-server status and displays the app in an iframe.

import { usePreviewStore } from "./store";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { usePolling } from "../../hooks/usePolling";
import "./preview.css";

export function PreviewPanel({ sessionId }: { sessionId: string }) {
  const { url, isRunning, loading, error } = usePreviewStore();
  const run = usePreviewStore((s) => s.run);
  const stop = usePreviewStore((s) => s.stop);

  // Poll the backend for dev-server status while mounted.
  usePolling(
    async () => {
      await usePreviewStore.getState().poll(sessionId);
    },
    { interval: 2000, enabled: true }
  );

  return (
    <div className="panel-preview preview-panel">
      <div className="preview-toolbar">
        <Button
          variant="primary"
          size="sm"
          onClick={() => run(sessionId)}
          disabled={isRunning || loading}
          loading={loading}
        >
          Run
        </Button>
        <Button variant="secondary" size="sm" onClick={() => stop(sessionId)} disabled={!isRunning}>
          Stop
        </Button>
        {isRunning && url && (
          <span className="preview-status">
            <span className="preview-status-dot" aria-hidden="true" />
            <span className="preview-status-url" title={url}>
              {url.replace(/^https?:\/\//, "")}
            </span>
          </span>
        )}
      </div>
      {error && (
        <div className="preview-alert">
          <ErrorBanner message={error} onRetry={() => run(sessionId)} />
        </div>
      )}
      {url ? (
        <iframe
          src={url}
          title="App preview"
          className="preview-frame"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        />
      ) : (
        <EmptyState title="No preview yet" body="Run the app to see a live preview here." />
      )}
    </div>
  );
}
