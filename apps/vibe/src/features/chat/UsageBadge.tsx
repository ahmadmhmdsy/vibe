// features/chat/UsageBadge.tsx — Usage statistics badge.
// Polls the backend for usage data and displays it in a compact format.

import { useState } from "react";
import { api, type UsageStats } from "../../lib/api";
import { usePolling } from "../../hooks/usePolling";

export function UsageBadge({ sessionId }: { sessionId: string }) {
  const [usage, setUsage] = useState<UsageStats | null>(null);

  usePolling(
    async () => {
      const data = await api.getUsage(sessionId);
      setUsage(data);
    },
    { interval: 5000, enabled: true }
  );

  if (!usage || usage.steps === 0) return null;

  const cost = usage.total_cost_usd ?? 0;
  const tokens = usage.total_tokens ?? 0;
  // Per-model detail lives in the tooltip so the badge stays one line.
  const breakdown = (usage.by_model ?? [])
    .map((m) => {
      const modelCost = m.cost_usd > 0 ? ` · $${m.cost_usd.toFixed(4)}` : "";
      return `${m.provider}/${m.model}: ${m.total_tokens.toLocaleString()} tokens${modelCost}`;
    })
    .join("\n");

  return (
    <div className="usage-badge" title={breakdown || undefined}>
      <span className="usage-badge-steps">{usage.steps} steps</span>
      <span className="usage-badge-separator">·</span>
      <span className="usage-badge-tokens">{tokens.toLocaleString()} tokens</span>
      {/* A free/local provider reports zero cost: an empty "$0.0000" is noise. */}
      {cost > 0 && (
        <>
          <span className="usage-badge-separator">·</span>
          <span className="usage-badge-cost">
            ${cost < 0.01 ? cost.toFixed(4) : cost.toFixed(2)}
          </span>
        </>
      )}
    </div>
  );
}
