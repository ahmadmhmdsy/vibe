// features/settings/SettingsPanel.tsx — Provider management UI.
// Lists built-in and custom providers, allows CRUD operations on custom providers.

import { useEffect, useState } from "react";
import { api, type CustomProvider, type CustomModel } from "../../lib/api";
import { useSettingsStore } from "./store";
import { Button } from "../../components/ui/Button";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { useToast } from "../../components/ui/Toast";
import "./settings.css";

const PROTOCOLS: CustomModel["protocol"][] = ["openai-chat", "openai-responses", "anthropic-messages"];

interface FormState {
  id: string | null;
  name: string;
  baseUrl: string;
  apiKey: string;
  models: CustomModel[];
}

const emptyForm: FormState = { id: null, name: "", baseUrl: "", apiKey: "", models: [] };

export function SettingsPanel() {
  const { providers, load } = useSettingsStore();
  const { toast } = useToast();
  const [customs, setCustoms] = useState<CustomProvider[]>([]);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<CustomProvider | null>(null);

  useEffect(() => { load().catch((e) => setError(e.message)); }, []);
  useEffect(() => { api.listProviders().then(setCustoms).catch((e) => setError(e.message)); }, []);

  const refreshCustoms = () => api.listProviders().then(setCustoms).catch((e) => setError(e.message));

  const startEdit = (p: CustomProvider) => {
    setForm({
      id: p.id,
      name: p.name,
      baseUrl: p.baseUrl,
      apiKey: "",
      models: p.models.map((m) => ({ ...m })),
    });
  };

  const save = async () => {
    if (!form.name.trim() || !form.baseUrl.trim()) {
      setError("Name and Base URL are required.");
      return;
    }
    setError(null);
    try {
      if (form.id) {
        await api.updateProvider(form.id, {
          name: form.name,
          baseUrl: form.baseUrl,
          apiKey: form.apiKey || undefined,
          models: form.models,
        });
      } else {
        await api.createProvider({
          name: form.name,
          baseUrl: form.baseUrl,
          apiKey: form.apiKey || undefined,
          models: form.models,
        });
      }
      setForm(emptyForm);
      await refreshCustoms();
      await load();
      toast(form.id ? "Provider updated" : "Provider added", "success");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save provider.");
    }
  };

  const doDelete = async () => {
    if (!confirmDelete) return;
    const id = confirmDelete.id;
    setConfirmDelete(null);
    try {
      await api.deleteProvider(id);
      await refreshCustoms();
      await load();
      toast("Provider deleted", "success");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete provider.");
    }
  };

  const setModel = (i: number, patch: Partial<CustomModel>) => {
    setForm((f) => ({ ...f, models: f.models.map((m, j) => (j === i ? { ...m, ...patch } : m)) }));
  };

  const cancel = () => {
    setForm(emptyForm);
    setError(null);
  };

  return (
    <div className="settings">
      <section>
        <h3>Built-in providers</h3>
        {providers.length === 0 ? (
          <p className="muted">No providers loaded</p>
        ) : (
          <ul className="provider-list">
            {providers.map((p) => (
              <li key={p.id} className="provider-row">
                <span className="provider-name">{p.name}</span>
                <span className={p.key_configured ? "key-badge key-badge-on" : "key-badge key-badge-off"}>
                  {p.key_configured ? "Key configured" : "No key"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3>Custom providers</h3>
        {customs.length === 0 && <p className="muted">No custom providers yet.</p>}
        {customs.map((p) => (
          <div key={p.id} className="provider-row">
            <span className="provider-name">
              {p.name} <span className="muted">({p.baseUrl})</span>
            </span>
            <span className="provider-actions">
              <Button variant="ghost" size="sm" onClick={() => startEdit(p)}>
                Edit
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(p)}>
                Delete
              </Button>
            </span>
          </div>
        ))}
      </section>

      <section>
        <h3>{form.id ? "Edit provider" : "Add provider"}</h3>
        <div className="settings-form">
          <label className="field">
            <span className="field-label">Name</span>
            <input placeholder="Name" aria-label="Provider name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <label className="field">
            <span className="field-label">Base URL</span>
            <input placeholder="Base URL" aria-label="Provider base URL" value={form.baseUrl} onChange={(e) => setForm({ ...form, baseUrl: e.target.value })} />
          </label>
          <label className="field">
            <span className="field-label">API key</span>
            <input placeholder="API key" aria-label="Provider API key" type="password" value={form.apiKey} onChange={(e) => setForm({ ...form, apiKey: e.target.value })} />
          </label>

          <div className="field">
            <span className="field-label">Models</span>
            {form.models.map((m, i) => (
              <div key={i} className="model-row">
                <input placeholder="id" aria-label={`Model ${i + 1} id`} value={m.id} onChange={(e) => setModel(i, { id: e.target.value })} />
                <input placeholder="name" aria-label={`Model ${i + 1} name`} value={m.name} onChange={(e) => setModel(i, { name: e.target.value })} />
                <select aria-label={`Model ${i + 1} protocol`} value={m.protocol} onChange={(e) => setModel(i, { protocol: e.target.value as CustomModel["protocol"] })}>
                  {PROTOCOLS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
                <Button variant="ghost" size="sm" aria-label={`Remove model ${i + 1}`} onClick={() => setForm((f) => ({ ...f, models: f.models.filter((_, j) => j !== i) }))}>
                  Remove
                </Button>
              </div>
            ))}
            <Button variant="ghost" size="sm" onClick={() => setForm((f) => ({ ...f, models: [...f.models, { id: "", name: "", protocol: "openai-chat" }] }))}>
              + Add model
            </Button>
          </div>

          {error && (
            <p className="settings-error" role="alert">
              {error}
            </p>
          )}

          <div className="settings-actions">
            <Button variant="primary" onClick={save}>
              Save
            </Button>
            <Button variant="secondary" onClick={cancel}>
              Cancel
            </Button>
          </div>
        </div>
      </section>

      <ConfirmDialog
        open={!!confirmDelete}
        onClose={() => setConfirmDelete(null)}
        onConfirm={doDelete}
        title="Delete provider?"
        body={`This removes ${confirmDelete?.name} and its models.`}
        confirmLabel="Delete"
      />
    </div>
  );
}
