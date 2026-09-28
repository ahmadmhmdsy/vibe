// apps/vibe/src/features/preview/PreviewPanel.tsx
import { usePreviewStore } from "./store";

export function PreviewPanel({ sessionId }: { sessionId: string }) {
  const { url, isRunning, run, stop } = usePreviewStore();
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", gap: 8, padding: 8 }}>
        <button onClick={run} disabled={isRunning}>Run</button>
        <button onClick={stop} disabled={!isRunning}>Stop</button>
      </div>
      {url ? (
        <iframe src={url} title="preview" style={{ flex: 1, border: "none" }} />
      ) : (
        <div style={{ flex: 1, display: "grid", placeItems: "center" }}>No preview yet</div>
      )}
    </div>
  );
}
