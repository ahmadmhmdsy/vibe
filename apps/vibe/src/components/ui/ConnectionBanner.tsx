// components/ui/ConnectionBanner.tsx — stream health with a way back.
// The SSE client used to stop retrying after five failures and leave the UI
// looking live; this is the surface that tells the user and offers a retry.

import { Button } from "./Button";
import type { StreamStatus } from "../../lib/sse";

export interface ConnectionBannerProps {
  status: StreamStatus;
  onRetry: () => void;
}

export function ConnectionBanner({ status, onRetry }: ConnectionBannerProps) {
  if (status !== "reconnecting" && status !== "lost") return null;

  const lost = status === "lost";
  return (
    <div className="connection-banner" role="alert">
      <span className="connection-banner-message">
        {lost
          ? "Live updates stopped. The chat may be out of date."
          : "Reconnecting to live updates..."}
      </span>
      {lost && (
        <Button variant="ghost" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
