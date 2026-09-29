// apps/vibe/src/features/sessions/SessionsPanel.tsx
import { useEffect, useState } from "react";
import { useSessionsStore } from "./store";
import { api, ApiError, type ProviderInfo, type Session } from "../../lib/api";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import "./sessions.css";

export function SessionsPanel() {
  const { sessions, activeId, load, create, remove, select } = useSessionsStore();
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<Session | null>(null);

  useEffect(() => {
    setLoading(true);
    load()
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load sessions."))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { api.getCatalog().then(setProviders).catch(() => {}); }, []);

  const modelLabel = (provider_id: string, model_id: string) => {
    const m = providers.find((p) => p.id === provider_id)?.models.find((m) => m.id === model_id);
    return m ? m.name : model_id;
  };

  const startRename = (s: Session) => {
    setEditingId(s.id);
    setEditTitle(s.title);
  };
  const commitRename = async (id: string) => {
    const title = editTitle.trim();
    setEditingId(null);
    if (title) await api.renameSession(id, title);
    await load();
  };

  const doDelete = async () => {
    if (!confirmDelete) return;
    const id = confirmDelete.id;
    setConfirmDelete(null);
    await remove(id);
  };

  return (
    <div className="sessions-panel">
      <div className="sessions-header">
        <span className="sessions-title">Sessions</span>
        <Button variant="primary" size="sm" onClick={() => create()}>
          New
        </Button>
      </div>

      {error && (
        <div className="sessions-alert">
          <ErrorBanner
            message={error}
            onRetry={() => {
              setError(null);
              setLoading(true);
              load()
                .catch((e) => setError(e instanceof Error ? e.message : "Failed to load sessions."))
                .finally(() => setLoading(false));
            }}
          />
        </div>
      )}

      <div className="sessions-list">
        {loading ? (
          <div className="sessions-loading">
            <Spinner size="sm" label="Loading sessions" />
          </div>
        ) : sessions.length === 0 ? (
          <EmptyState
            title="No sessions yet"
            body="Start a new session and describe the app you want to build."
            action={
              <Button variant="primary" size="sm" onClick={() => create()}>
                New session
              </Button>
            }
          />
        ) : (
          sessions.map((s) => (
            <div
              key={s.id}
              className={s.id === activeId ? "session-row session-row-active" : "session-row"}
            >
              {editingId === s.id ? (
                <input
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitRename(s.id);
                    if (e.key === "Escape") setEditingId(null);
                  }}
                  onBlur={() => commitRename(s.id)}
                  autoFocus
                  aria-label="Session title"
                  className="session-rename-input"
                />
              ) : (
                <>
                  <button
                    className="session-select"
                    onClick={() => select(s.id)}
                  >
                    <span className="session-name">{s.title}</span>
                    <span className="session-meta">
                      {modelLabel(s.model.provider_id, s.model.model_id)}
                      {" · "}
                      {new Date(s.updated_at).toLocaleString()}
                    </span>
                  </button>
                  <div className="session-actions">
                    <Button variant="ghost" size="sm" onClick={() => startRename(s)}>
                      Rename
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`Delete ${s.title}`}
                      className="session-delete"
                      onClick={() => setConfirmDelete(s)}
                    >
                      Delete
                    </Button>
                  </div>
                </>
              )}
            </div>
          ))
        )}
      </div>

      <ConfirmDialog
        open={!!confirmDelete}
        onClose={() => setConfirmDelete(null)}
        onConfirm={doDelete}
        title="Delete session?"
        body="This permanently removes the session and its history."
        confirmLabel="Delete"
      />
    </div>
  );
}
