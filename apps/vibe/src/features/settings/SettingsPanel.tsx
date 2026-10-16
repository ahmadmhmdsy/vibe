// features/settings/SettingsPanel.tsx — the settings surface, split into tabs.
//
// The shell owns the dialog (App.tsx renders this inside a Modal), so this file
// renders sections only: no dialog, no page title, no modal. Providers and the
// system prompt each get a tab instead of one long scroll.
//
// Nothing here ever receives a stored API key back from the server. The catalog
// reports only whether one is configured, so every key input is write-only and
// always renders empty.

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  api,
  type CustomModel,
  type CustomProvider,
  type ProviderInfo,
  type SystemPromptSettings,
} from "../../lib/api";
import { useSettingsStore } from "./store";
import {
  Badge,
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorBanner,
  IconButton,
  Skeleton,
  TabPanel,
  Tabs,
  useToast,
} from "../../components/ui";
import { Icon } from "../../components/icons/Icon";
import "./settings.css";

const PROTOCOLS: CustomModel["protocol"][] = [
  "openai-chat",
  "openai-responses",
  "anthropic-messages",
];

type TabId = "providers" | "system-prompt";

interface FormState {
  id: string | null;
  name: string;
  baseUrl: string;
  apiKey: string;
  models: CustomModel[];
}

const emptyForm: FormState = { id: null, name: "", baseUrl: "", apiKey: "", models: [] };

/** Run after the browser has painted the next frame.
 *
 * The Modal focuses its own first tabbable element in a passive effect, which
 * runs after this component's layout effects, so focusing synchronously would
 * be overwritten by the dialog. One frame is enough for the dialog to place its
 * focus; the timeout fallback keeps environments without rAF working. */
function nextFrame(callback: () => void): () => void {
  if (typeof requestAnimationFrame === "function") {
    const id = requestAnimationFrame(callback);
    return () => cancelAnimationFrame(id);
  }
  const id = window.setTimeout(callback, 0);
  return () => window.clearTimeout(id);
}

/** The one line that tells the user which layer is winning (BE-19).
 *
 * An environment-set prompt cannot be overridden from here, so saying so is not
 * decoration: without it the field looks broken when a save changes nothing. */
function sourceLabel(prompt: SystemPromptSettings["system_prompt"] | null): string {
  if (!prompt) return "Loading the system prompt...";
  if (prompt.source === "env") {
    return "Set by VIBE_SYSTEM_PROMPT, which wins over this field. The editor is read-only while it is set.";
  }
  if (prompt.source === "file") {
    return "Saved on this machine. This override applies to every turn.";
  }
  return "Using the built-in default. Save a prompt to override it.";
}

export function SettingsPanel({ focusProviders = false }: { focusProviders?: boolean }) {
  const { providers, load } = useSettingsStore();
  const { toast } = useToast();

  const [tab, setTab] = useState<TabId>("providers");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [customs, setCustoms] = useState<CustomProvider[]>([]);
  // One draft per provider id. Kept apart from the server state so a typed key
  // is never mistaken for a stored one.
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({});
  const [keyBusy, setKeyBusy] = useState<string | null>(null);
  const [keyError, setKeyError] = useState<string | null>(null);
  // Initialised from the prop, not set from an effect: the first-run panel sent
  // the user here to configure a provider, so the form is already open.
  const [formOpen, setFormOpen] = useState(focusProviders);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<CustomProvider | null>(null);
  const [prompt, setPrompt] = useState<SystemPromptSettings["system_prompt"] | null>(null);
  const [promptText, setPromptText] = useState("");
  const [promptLoading, setPromptLoading] = useState(true);
  const [promptError, setPromptError] = useState<string | null>(null);
  const [promptBusy, setPromptBusy] = useState<"save" | "reset" | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const didFocusRef = useRef(false);

  // Every write happens after an await, so nothing is set during the effect's
  // synchronous pass (the set-state-in-effect lint rule protects that).
  const fetchProviders = useCallback(async () => {
    try {
      const [, list] = await Promise.all([load(), api.listProviders()]);
      setCustoms(list);
      setLoadError(null);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Failed to load providers.");
    } finally {
      setLoading(false);
    }
  }, [load]);

  const fetchPrompt = useCallback(async () => {
    try {
      const s = await api.getSettings();
      setPrompt(s.system_prompt);
      setPromptText(s.system_prompt.effective);
      setPromptError(null);
    } catch (e) {
      setPromptError(e instanceof Error ? e.message : "Failed to load the system prompt.");
    } finally {
      setPromptLoading(false);
    }
  }, []);

  // The async wrapper matters: it keeps every state write off the effect's
  // synchronous pass, which is exactly what react-hooks/set-state-in-effect is
  // about. The loaders themselves already await before setting anything.
  useEffect(() => {
    void (async () => {
      await fetchProviders();
    })();
  }, [fetchProviders]);

  useEffect(() => {
    void (async () => {
      await fetchPrompt();
    })();
  }, [fetchPrompt]);

  /** Re-read the provider lists after a change, without the loading flash. */
  const refreshProviders = useCallback(async () => {
    const [, list] = await Promise.all([load(), api.listProviders()]);
    setCustoms(list);
  }, [load]);

  const retryProviders = () => {
    setLoading(true);
    setLoadError(null);
    void fetchProviders();
  };

  const retryPrompt = () => {
    setPromptLoading(true);
    setPromptError(null);
    void fetchPrompt();
  };

  // The first-run panel sends the user here for one reason, so land them on the
  // field that reason is about. useLayoutEffect because the Modal places its own
  // focus in a passive effect; one frame lets that finish first.
  useLayoutEffect(() => {
    if (!focusProviders || didFocusRef.current) return;
    return nextFrame(() => {
      const target = nameRef.current;
      if (!target) return;
      didFocusRef.current = true;
      target.focus();
      target.scrollIntoView?.({ block: "center" });
    });
  }, [focusProviders, formOpen]);

  const openForm = (state: FormState) => {
    setForm(state);
    setFormError(null);
    setFormOpen(true);
    nextFrame(() => nameRef.current?.focus());
  };

  const startEdit = (p: CustomProvider) => {
    openForm({
      id: p.id,
      name: p.name,
      baseUrl: p.baseUrl,
      apiKey: "",
      models: p.models.map((m) => ({ ...m })),
    });
  };

  const setModel = (index: number, patch: Partial<CustomModel>) => {
    setForm((f) => ({
      ...f,
      models: f.models.map((m, i) => (i === index ? { ...m, ...patch } : m)),
    }));
  };

  /** The key write shared by save and clear.
   *
   * `apiKey: ""` is the only way to ask the backend to forget a stored key;
   * omitting the field leaves it untouched, which is why the save path always
   * sends a non-empty value. */
  const mutateKey = async (p: CustomProvider, apiKey: string, okMessage: string) => {
    setKeyError(null);
    setKeyBusy(p.id);
    try {
      await api.updateProvider(p.id, { apiKey });
      setKeyDrafts((drafts) => ({ ...drafts, [p.id]: "" }));
      await refreshProviders();
      toast(okMessage, "success");
    } catch (e) {
      setKeyError(e instanceof Error ? e.message : "Failed to save the API key.");
    } finally {
      setKeyBusy(null);
    }
  };

  const saveForm = async () => {
    const name = form.name.trim();
    const baseUrl = form.baseUrl.trim();
    if (!name || !baseUrl) {
      setFormError("Name and base URL are required.");
      return;
    }
    setFormError(null);
    try {
      if (form.id) {
        await api.updateProvider(form.id, { name, baseUrl, models: form.models });
      } else {
        await api.createProvider({
          name,
          baseUrl,
          apiKey: form.apiKey || undefined,
          models: form.models,
        });
      }
      const message = form.id ? "Provider updated" : "Provider added";
      setForm(emptyForm);
      setFormOpen(false);
      await refreshProviders();
      toast(message, "success");
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Failed to save the provider.");
    }
  };

  const doDelete = async () => {
    if (!confirmDelete) return;
    const { id } = confirmDelete;
    setConfirmDelete(null);
    try {
      await api.deleteProvider(id);
      await refreshProviders();
      toast("Provider deleted", "success");
    } catch (e) {
      setKeyError(e instanceof Error ? e.message : "Failed to delete the provider.");
    }
  };

  const savePrompt = async (value: string) => {
    setPromptError(null);
    setPromptBusy(value ? "save" : "reset");
    try {
      const s = await api.setSystemPrompt(value);
      setPrompt(s.system_prompt);
      setPromptText(s.system_prompt.effective);
      toast(value ? "System prompt saved" : "System prompt reset to the default", "success");
    } catch (e) {
      setPromptError(e instanceof Error ? e.message : "Failed to save the system prompt.");
    } finally {
      setPromptBusy(null);
    }
  };

  const customById = new Map(customs.map((c) => [c.id, c]));
  // The catalog is the complete list, but /providers carries the base URL and
  // protocol the catalog omits. If the catalog read is empty while a custom
  // provider exists, show it rather than hiding a provider the server returned.
  const rows: ProviderInfo[] =
    providers.length > 0
      ? providers
      : customs.map((c) => ({
          id: c.id,
          name: c.name,
          capabilities: { tool_support: true, vision: false },
          models: c.models.map((m) => ({ id: m.id, name: m.name })),
          key_configured: c.key_configured,
        }));

  const promptEnvLocked = prompt?.source === "env";

  return (
    <div className="settings">
      <Tabs
        items={[
          { id: "providers", label: "Providers" },
          { id: "system-prompt", label: "System prompt" },
        ]}
        value={tab}
        onChange={(id) => setTab(id as TabId)}
        label="Settings sections"
        idPrefix="settings"
      />

      <TabPanel id="providers" idPrefix="settings" active={tab === "providers"}>
        <div className="settings-tab-body">
          <div className="panel-header settings-section-header">
            <h3 className="panel-title">Providers</h3>
            <div className="panel-header-spacer" />
            <div className="panel-actions">
              <Button
                size="sm"
                variant="secondary"
                aria-expanded={formOpen}
                onClick={() => openForm(emptyForm)}
              >
                Add provider
              </Button>
            </div>
          </div>

          {loading ? (
            <div className="settings-skeleton">
              <span className="sr-only">Loading providers</span>
              {[0, 1, 2].map((i) => (
                <div key={i} className="settings-skeleton-row">
                  <Skeleton width="40%" height="14px" />
                  <Skeleton width="96px" height="20px" />
                  <Skeleton width="100%" height="32px" />
                </div>
              ))}
            </div>
          ) : loadError ? (
            <div className="settings-section-body">
              <ErrorBanner message={loadError} onRetry={retryProviders} />
            </div>
          ) : (
            <div className="settings-section-body">
              {keyError ? (
                <p className="settings-error" role="alert">
                  {keyError}
                </p>
              ) : null}

              {rows.length === 0 ? (
                <EmptyState
                  headingLevel="h4"
                  title="No providers"
                  body="The server returned an empty provider catalog."
                  action={
                    <Button size="sm" variant="secondary" onClick={retryProviders}>
                      Reload
                    </Button>
                  }
                />
              ) : (
                <ul className="provider-rows">
                  {rows.map((p) => {
                    const custom = customById.get(p.id);
                    const keyInputId = `provider-key-${p.id}`;
                    const keyHintId = `provider-key-hint-${p.id}`;
                    return (
                      <li key={p.id} className="provider-row">
                        <div className="provider-row-main">
                          <span className="provider-name">{p.name}</span>
                          <Badge tone={p.key_configured ? "success" : "neutral"}>
                            {p.key_configured ? "Key configured" : "No key"}
                          </Badge>
                          {custom ? (
                            <span className="provider-base mono">{custom.baseUrl}</span>
                          ) : null}
                          <span className="provider-row-spacer" />
                          {custom ? (
                            <div className="provider-row-actions">
                              <Button size="sm" variant="ghost" onClick={() => startEdit(custom)}>
                                Edit
                              </Button>
                              <IconButton
                                label={`Delete ${p.name}`}
                                onClick={() => setConfirmDelete(custom)}
                              >
                                <Icon name="trash" size={14} />
                              </IconButton>
                            </div>
                          ) : null}
                        </div>

                        {custom ? (
                          <div className="field">
                            <label className="field-label" htmlFor={keyInputId}>
                              API key
                              <span className="sr-only"> for {p.name}</span>
                            </label>
                            <div className="provider-key-controls">
                              <input
                                id={keyInputId}
                                type="password"
                                autoComplete="off"
                                placeholder={
                                  p.key_configured
                                    ? "Leave blank to keep the stored key"
                                    : "Paste a key"
                                }
                                value={keyDrafts[p.id] ?? ""}
                                onChange={(event) =>
                                  setKeyDrafts((drafts) => ({
                                    ...drafts,
                                    [p.id]: event.target.value,
                                  }))
                                }
                              />
                              <Button
                                size="sm"
                                variant="secondary"
                                loading={keyBusy === p.id}
                                disabled={(keyDrafts[p.id] ?? "") === ""}
                                onClick={() =>
                                  void mutateKey(custom, keyDrafts[p.id] ?? "", "API key saved")
                                }
                              >
                                Save key
                              </Button>
                              {p.key_configured ? (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => void mutateKey(custom, "", "API key cleared")}
                                >
                                  Clear key
                                </Button>
                              ) : null}
                            </div>
                          </div>
                        ) : (
                          <div className="field">
                            <label className="field-label" htmlFor={keyInputId}>
                              API key
                              <span className="sr-only"> for {p.name}</span>
                            </label>
                            {/* A built-in provider's key comes from the server
                                environment, so the field is read-only for the
                                same reason the system prompt is: it must not
                                look like a box whose value could take effect. */}
                            <input
                              id={keyInputId}
                              type="password"
                              value=""
                              readOnly
                              disabled
                              placeholder="Set by the server environment"
                              aria-describedby={keyHintId}
                            />
                            <p className="field-hint" id={keyHintId}>
                              Built-in provider keys are read from the server environment and are
                              never stored by the app.
                            </p>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          )}

          {formOpen ? (
            <section className="settings-form-section" aria-labelledby="provider-form-title">
              <div className="panel-header settings-section-header">
                <h3 className="panel-title" id="provider-form-title">
                  {form.id ? "Edit provider" : "Add provider"}
                </h3>
              </div>
              <div className="settings-section-body">
                <div className="settings-form">
                  <div className="field">
                    <label className="field-label" htmlFor="provider-name">
                      Name
                    </label>
                    <input
                      id="provider-name"
                      ref={nameRef}
                      value={form.name}
                      onChange={(event) => setForm({ ...form, name: event.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label className="field-label" htmlFor="provider-base-url">
                      Base URL
                    </label>
                    <input
                      id="provider-base-url"
                      value={form.baseUrl}
                      onChange={(event) => setForm({ ...form, baseUrl: event.target.value })}
                    />
                  </div>
                  {form.id ? null : (
                    <div className="field">
                      <label className="field-label" htmlFor="provider-api-key">
                        API key
                      </label>
                      <input
                        id="provider-api-key"
                        type="password"
                        autoComplete="off"
                        value={form.apiKey}
                        placeholder="Paste a key, or leave blank for a local endpoint"
                        onChange={(event) => setForm({ ...form, apiKey: event.target.value })}
                      />
                    </div>
                  )}

                  <fieldset className="field settings-models">
                    <legend className="field-label">Models</legend>
                    {form.models.map((m, i) => (
                      <div key={i} className="model-row">
                        <label className="sr-only" htmlFor={`model-id-${i}`}>
                          Model {i + 1} id
                        </label>
                        <input
                          id={`model-id-${i}`}
                          placeholder="id"
                          value={m.id}
                          onChange={(event) => setModel(i, { id: event.target.value })}
                        />
                        <label className="sr-only" htmlFor={`model-name-${i}`}>
                          Model {i + 1} name
                        </label>
                        <input
                          id={`model-name-${i}`}
                          placeholder="name"
                          value={m.name}
                          onChange={(event) => setModel(i, { name: event.target.value })}
                        />
                        <label className="sr-only" htmlFor={`model-protocol-${i}`}>
                          Model {i + 1} protocol
                        </label>
                        <select
                          id={`model-protocol-${i}`}
                          value={m.protocol}
                          onChange={(event) =>
                            setModel(i, { protocol: event.target.value as CustomModel["protocol"] })
                          }
                        >
                          {PROTOCOLS.map((protocol) => (
                            <option key={protocol} value={protocol}>
                              {protocol}
                            </option>
                          ))}
                        </select>
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Remove model ${i + 1}`}
                          onClick={() =>
                            setForm((f) => ({
                              ...f,
                              models: f.models.filter((_, j) => j !== i),
                            }))
                          }
                        >
                          Remove
                        </Button>
                      </div>
                    ))}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        setForm((f) => ({
                          ...f,
                          models: [...f.models, { id: "", name: "", protocol: "openai-chat" }],
                        }))
                      }
                    >
                      Add model
                    </Button>
                  </fieldset>

                  {formError ? (
                    <p className="settings-error" role="alert">
                      {formError}
                    </p>
                  ) : null}

                  <div className="settings-actions">
                    <Button variant="primary" onClick={() => void saveForm()}>
                      Save
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setForm(emptyForm);
                        setFormError(null);
                        setFormOpen(false);
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              </div>
            </section>
          ) : null}
        </div>
      </TabPanel>

      <TabPanel id="system-prompt" idPrefix="settings" active={tab === "system-prompt"}>
        <div className="settings-tab-body">
          <div className="panel-header settings-section-header">
            <h3 className="panel-title">System prompt</h3>
            <div className="panel-header-spacer" />
            <div className="panel-actions">
              <Badge tone={prompt?.source === "env" ? "info" : "neutral"}>
                {prompt?.source === "env"
                  ? "From the environment"
                  : prompt?.source === "file"
                    ? "Saved override"
                    : "Built-in default"}
              </Badge>
            </div>
          </div>

          <div className="settings-section-body">
            {promptLoading ? (
              <div className="settings-skeleton">
                <span className="sr-only">Loading the system prompt</span>
                <Skeleton width="70%" height="14px" />
                <Skeleton width="100%" height="120px" />
              </div>
            ) : promptError && !prompt ? (
              <ErrorBanner message={promptError} onRetry={retryPrompt} />
            ) : (
              <>
                <p className="settings-source muted" data-testid="system-prompt-source">
                  {sourceLabel(prompt)}
                </p>

                {promptError ? (
                  <p className="settings-error" role="alert">
                    {promptError}
                  </p>
                ) : null}

                <div className="field">
                  <label className="field-label" htmlFor="system-prompt">
                    System prompt
                  </label>
                  <textarea
                    id="system-prompt"
                    className="system-prompt-input"
                    rows={8}
                    value={promptText}
                    disabled={promptEnvLocked}
                    onChange={(event) => setPromptText(event.target.value)}
                  />
                </div>

                {/* Three layers can supply this prompt. The field shows what
                    wins; this shows what the fallback would be. */}
                {prompt ? (
                  <details className="settings-default">
                    <summary className="settings-default-summary">Built-in default prompt</summary>
                    <p className="settings-default-value mono" data-testid="system-prompt-default">
                      {prompt.default}
                    </p>
                  </details>
                ) : null}

                <div className="settings-actions">
                  <Button
                    variant="primary"
                    loading={promptBusy === "save"}
                    disabled={promptEnvLocked || promptBusy !== null}
                    onClick={() => void savePrompt(promptText)}
                  >
                    Save prompt
                  </Button>
                  <Button
                    variant="secondary"
                    loading={promptBusy === "reset"}
                    disabled={promptEnvLocked || promptBusy !== null || prompt?.source !== "file"}
                    onClick={() => void savePrompt("")}
                  >
                    Reset to default
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      </TabPanel>

      <ConfirmDialog
        open={!!confirmDelete}
        onClose={() => setConfirmDelete(null)}
        onConfirm={() => void doDelete()}
        title="Delete provider?"
        body={`This removes ${confirmDelete?.name ?? "the provider"} and its models.`}
        confirmLabel="Delete"
      />
    </div>
  );
}
