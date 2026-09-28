// apps/vibe/src/features/chat/ModelPicker.tsx
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { ProviderInfo } from "../../lib/api";
import { useChatStore } from "./store";

export function ModelPicker() {
  const { model, setModel } = useChatStore();
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  useEffect(() => { api.getCatalog().then(setProviders).catch(() => {}); }, []);
  return (
    <select
      aria-label="Model"
      value={`${model.provider_id}/${model.model_id}`}
      onChange={(e) => {
        const [provider_id, model_id] = e.target.value.split("/");
        setModel({ provider_id, model_id });
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
