// apps/vibe/src/features/chat/ModelPicker.tsx
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { ProviderInfo } from "../../lib/api";
import { useChatStore } from "./store";

export function ModelPicker({ sessionId }: { sessionId: string | null }) {
  const { model, setModel } = useChatStore();
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  useEffect(() => { api.getCatalog().then(setProviders).catch(() => {}); }, []);

  // Reflect the active session's stored model when the session changes.
  useEffect(() => {
    if (!sessionId) return;
    api.getSession(sessionId)
      .then((s) => setModel({ provider_id: s.model.provider_id, model_id: s.model.model_id }))
      .catch(() => {});
  }, [sessionId]);

  return (
    <select
      aria-label="Model"
      value={`${model.provider_id}/${model.model_id}`}
      onChange={(e) => {
        const [provider_id, model_id] = e.target.value.split("/");
        setModel({ provider_id, model_id });
        if (sessionId) api.setSessionModel(sessionId, { provider_id, model_id }).catch(() => {});
      }}
      style={{ padding: 4 }}
    >
      {providers.map((p) => (
        <optgroup key={p.id} label={p.name}>
          {p.models.map((m) => (
            <option key={m.id} value={`${p.id}/${m.id}`}>{m.name}</option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
