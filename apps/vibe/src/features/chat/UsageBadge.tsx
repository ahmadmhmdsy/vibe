// apps/vibe/src/features/chat/UsageBadge.tsx
import { useEffect, useState } from "react";
import { api, type UsageStats } from "../../lib/api";

export function UsageBadge({ sessionId }: { sessionId: string }) {
  const [usage, setUsage] = useState<UsageStats | null>(null);

  useEffect(() => {
    api.getUsage(sessionId).then(setUsage).catch(() => {});
    const t = setInterval(() => {
      api.getUsage(sessionId).then(setUsage).catch(() => {});
    }, 5000);
    return () => clearInterval(t);
  }, [sessionId]);

  if (!usage || usage.steps === 0) return null;
  return (
    <div style={{ padding: "4px 8px", fontSize: 12, color: "#595959", borderTop: "1px solid #eee" }}>
      {usage.steps} steps · {usage.total_tokens.toLocaleString()} tokens · ${usage.total_cost_usd.toFixed(4)}
    </div>
  );
}
