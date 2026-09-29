// apps/vibe/src/features/preview/PreviewPanel.tsx
import { useEffect } from "react";
import { usePreviewStore } from "./store";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import "./preview.css";

export function PreviewPanel({ sessionId }: { sessionId: string }) {
  const { url, isRunning, loading, error } = usePreviewStore();
  const run = usePreviewStore((s) => s.run);
  const stop = usePreviewStore((s) => s.stop);
  const poll = usePreviewStore((s) => s.poll);

  // Poll the backend for dev-server status while mounted.
  useEffect(() => {
    poll(sessionId).catch(() => {});
    const t = setInterval(() => poll(sessionId).catch(() => {}), 2000);
    return () => clearInterval(t);
  }, [sessionId]);

  return (
    <div className="panel-preview preview-panel">
      <div className="preview-toolbar">
        <Button variant="primary" size="sm" onClick={() => run(sessionId)} disabled={isRunning || loading} loading={loading}>
          Run
        </Button>
        <Button variant="secondary" size="sm" onClick={() => stop(sessionId)} disabled={!isRunning}>
          Stop
        </Button>
      </div>
      {error && (
        <div className="preview-alert">
          <ErrorBanner message={error} onRetry={() => run(sessionId)} />
        </div>
      )}
      {url ? (
        <iframe src={url} title="App preview" className="preview-frame" />
      ) : (
        <EmptyState
          title="No preview yet"
          body="Run the app to see a live preview here."
        />
      )}
    </div>
  );
}
