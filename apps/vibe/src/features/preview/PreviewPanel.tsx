// apps/vibe/src/features/preview/PreviewPanel.tsx
import { usePreviewStore } from "./store";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import "./preview.css";

export function PreviewPanel({ sessionId }: { sessionId: string }) {
  const { url, isRunning, loading, error, run, stop } = usePreviewStore();
  return (
    <div className="panel-preview preview-panel">
      <div className="preview-toolbar">
        <Button variant="primary" size="sm" onClick={run} disabled={isRunning || loading} loading={loading}>
          Run
        </Button>
        <Button variant="secondary" size="sm" onClick={stop} disabled={!isRunning}>
          Stop
        </Button>
      </div>
      {error && (
        <div className="preview-alert">
          <ErrorBanner message={error} onRetry={run} />
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
