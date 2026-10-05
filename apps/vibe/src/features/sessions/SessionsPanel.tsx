// features/sessions/SessionsPanel.tsx — Session management sidebar.
// Lists sessions, allows create/rename/delete, and shows model info.

import { useEffect, useState, useMemo } from "react";
import { useSessionsStore } from "./store";
import { api, type ProviderInfo, type Session } from "../../lib/api";
import { formatRelativeTime } from "../../lib/format";
import { Button } from "../../components/ui/Button";
import { IconButton } from "../../components/ui/IconButton";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { useToast } from "../../components/ui/Toast";
import "./sessions.css";

export function SessionsPanel() {
  const { sessions, activeId, load, create, remove, select } = useSessionsStore();
  const { toast } = useToast();
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [originalTitle, setOriginalTitle] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<Session | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const refresh = () =>
    load()
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load sessions."))
      .finally(() => setLoading(false));

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    api
      .getCatalog()
      .then(setProviders)
      .catch(() => {});
  }, []);

  const modelLabel = (provider_id: string, model_id: string) => {
    const m = providers.find((p) => p.id === provider_id)?.models.find((m) => m.id === model_id);
    return m ? m.name : model_id;
  };

  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase();
    return sessions.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        modelLabel(s.model.provider_id, s.model.model_id).toLowerCase().includes(q)
    );
  }, [sessions, searchQuery, providers]);

  const startRename = (s: Session) => {
    setEditingId(s.id);
    setEditTitle(s.title);
    setOriginalTitle(s.title);
  };

  const commitRename = async (id: string) => {
    const title = editTitle.trim();
    setEditingId(null);
    if (title && title !== originalTitle) {
      try {
        await api.renameSession(id, title);
        await load();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to rename the session.");
      }
    }
  };

  const cancelRename = () => {
    setEditTitle(originalTitle);
    setEditingId(null);
  };

  const onCreate = async () => {
    try {
      await create();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create a session.");
    }
  };

  const doDelete = async () => {
    if (!confirmDelete) return;
    const { id, title } = confirmDelete;
    setConfirmDelete(null);
    try {
      await remove(id);
      toast(`Deleted "${title}"`, "success");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete the session.");
    }
  };

  const exportSessions = () => {
    const data = JSON.stringify(sessions, null, 2);
    const blob = new Blob([data], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `vibe-sessions-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="sessions-panel">
      <div className="sessions-header">
        <span className="sessions-title">Sessions</span>
        <div className="sessions-header-actions">
          <Button
            variant="ghost"
            size="sm"
            onClick={exportSessions}
            disabled={sessions.length === 0}
          >
            Export
          </Button>
          <Button variant="primary" size="sm" onClick={onCreate}>
            New
          </Button>
        </div>
      </div>

      <div className="sessions-search">
        <input
          type="search"
          placeholder="Search sessions..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          aria-label="Search sessions"
          className="sessions-search-input"
        />
      </div>

      {error && (
        <div className="sessions-alert">
          <ErrorBanner
            message={error}
            onRetry={() => {
              setError(null);
              setLoading(true);
              refresh();
            }}
          />
        </div>
      )}

      <div className="sessions-list">
        {loading ? (
          <div className="sessions-loading">
            <Spinner size="sm" label="Loading sessions" />
          </div>
        ) : error ? null : filteredSessions.length === 0 ? (
          searchQuery ? (
            <EmptyState title="No matching sessions" body={`No sessions match "${searchQuery}".`} />
          ) : (
            <EmptyState
              title="No sessions yet"
              body="Start a new session and describe the app you want to build."
              action={
                <Button variant="primary" size="sm" onClick={onCreate}>
                  New session
                </Button>
              }
            />
          )
        ) : (
          filteredSessions.map((s) => (
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
                    if (e.key === "Escape") cancelRename();
                  }}
                  onBlur={() => commitRename(s.id)}
                  autoFocus
                  aria-label="Session title"
                  className="session-rename-input"
                />
              ) : (
                <>
                  <button className="session-select" onClick={() => select(s.id)}>
                    <span className="session-name" title={s.title}>
                      {s.title}
                    </span>
                    <span className="session-meta" title={new Date(s.updated_at).toLocaleString()}>
                      {modelLabel(s.model.provider_id, s.model.model_id)}
                      {" · "}
                      {formatRelativeTime(s.updated_at)}
                    </span>
                  </button>
                  <div className="session-actions">
                    <IconButton label="Rename" onClick={() => startRename(s)}>
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 16 16"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        aria-hidden="true"
                      >
                        <path
                          d="M11.2 2.3l2.5 2.5L5.4 13l-3 .6.6-3 8.2-8.3z"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </IconButton>
                    <IconButton
                      label={`Delete ${s.title}`}
                      className="session-delete"
                      onClick={() => setConfirmDelete(s)}
                    >
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 16 16"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        aria-hidden="true"
                      >
                        <path
                          d="M2.8 4.5h10.4M6.3 4.5V3h3.4v1.5M4.4 4.5l.7 9h5.8l.7-9"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </IconButton>
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
