// features/chat/ModelPicker.tsx — Model selection dropdown.
// Fetches available providers and models, allows selection per session.

import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { ProviderInfo } from "../../lib/api";
import { useChatStore } from "./store";

export function ModelPicker({ sessionId }: { sessionId: string | null }) {
  const { model, setModel } = useChatStore();
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getCatalog()
      .then(setProviders)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Reflect the active session's stored model when the session changes.
  useEffect(() => {
    if (!sessionId) return;
    api
      .getSession(sessionId)
      .then((s) => setModel({ provider_id: s.model.provider_id, model_id: s.model.model_id }))
      .catch(() => {});
  }, [sessionId]);

  // Carry the ids as data. Deriving them by splitting the option value on "/"
  // truncated any model id that itself contains a slash.
  const options = providers.flatMap((p) =>
    p.models.map((m) => ({
      value: `${p.id}/${m.id}`,
      provider_id: p.id,
      model_id: m.id,
      name: m.name,
      provider: p.name,
    }))
  );
  const current = `${model.provider_id}/${model.model_id}`;
  const currentExists = options.some((o) => o.value === current);

  return (
    <div className="model-picker">
      <label className="model-picker-label" htmlFor="model-select">
        Model
      </label>
      <select
        id="model-select"
        className="model-picker-select"
        value={currentExists ? current : ""}
        disabled={loading}
        onChange={(e) => {
          const picked = options.find((o) => o.value === e.target.value);
          if (!picked) return;
          const next = { provider_id: picked.provider_id, model_id: picked.model_id };
          setModel(next);
          if (sessionId) api.setSessionModel(sessionId, next).catch(() => {});
        }}
      >
        {!currentExists && (
          <option value="">
            {loading
              ? "Loading models..."
              : providers.length === 0
                ? "No providers configured"
                : "Select a model"}
          </option>
        )}
        {providers.map((p) => (
          <optgroup key={p.id} label={p.name}>
            {p.models.map((m) => (
              <option key={m.id} value={`${p.id}/${m.id}`}>
                {m.name}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </div>
  );
}
