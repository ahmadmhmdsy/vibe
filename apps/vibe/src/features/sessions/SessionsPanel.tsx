// features/sessions/SessionsPanel.tsx — Session management sidebar.
// Lists sessions grouped by recency, filters them, and owns rename/export/delete.

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useSessionsStore } from "./store";
import { NewSessionDialog } from "./NewSessionDialog";
import { api, type ProjectSource, type ProviderInfo, type Session } from "../../lib/api";
import { formatRelativeTime } from "../../lib/format";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorBanner,
  Menu,
  SearchField,
  Spinner,
  useToast,
} from "../../components/ui";
import { Icon } from "../../components/icons/Icon";
import "./sessions.css";

/** Recency buckets, in the order they render. Label wording is product copy. */
const BUCKETS = [
  { id: "today", label: "Today" },
  { id: "yesterday", label: "Yesterday" },
  { id: "week", label: "Previous 7 days" },
  { id: "month", label: "Previous 30 days" },
  { id: "older", label: "Older" },
] as const;

type BucketId = (typeof BUCKETS)[number]["id"];

const DAY_MS = 24 * 60 * 60 * 1000;

function midnight(value: number): number {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
  return date.getTime();
}

/**
 * Calendar-day distance, not elapsed hours: a session touched at 23:00
 * yesterday still reads "Yesterday" at 01:00 today, which is what the label
 * promises. A session with no usable timestamp cannot be placed by recency, so
 * it lands in the tail bucket instead of disappearing from the list.
 */
function bucketFor(iso: string | undefined, now: number): BucketId {
  if (!iso) return "older";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "older";
  // Rounding absorbs the 23- and 25-hour days a DST boundary produces.
  const days = Math.round((midnight(now) - midnight(then)) / DAY_MS);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days <= 7) return "week";
  if (days <= 30) return "month";
  return "older";
}

interface Group {
  id: BucketId;
  label: string;
  sessions: Session[];
}

/** Only non-empty buckets are returned, in declared order. */
function groupByRecency(sessions: readonly Session[], now: number): Group[] {
  const byBucket = new Map<BucketId, Session[]>();
  for (const session of sessions) {
    const id = bucketFor(session.updated_at ?? session.created_at, now);
    const bucket = byBucket.get(id);
    if (bucket) bucket.push(session);
    else byBucket.set(id, [session]);
  }
  return BUCKETS.flatMap((bucket) => {
    const list = byBucket.get(bucket.id);
    return list ? [{ ...bucket, sessions: list }] : [];
  });
}

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
  // The chooser is where a new workspace's origin is picked (M8/C1); the
  // keyboard shortcut and the empty-conversation CTA still create an empty one
  // directly, because that is the common case and a shortcut should not ask.
  const [newSession, setNewSession] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  // Buckets and relative timestamps are functions of "now". Keeping the clock
  // in state instead of calling Date.now() during render means an unrelated
  // re-render cannot re-bucket a row the user is looking at, and lets the
  // labels refresh while the panel sits open.
  const [now, setNow] = useState(() => Date.now());
  // Which row owns the roving tabindex. Deliberately not the same as the
  // selected session: arrow keys are for browsing, Enter/Space for choosing.
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const listRef = useRef<HTMLElement>(null);
  // Written as the inline editor closes and read by the effect below, so focus
  // can return to the row without a state round-trip.
  const restoreFocusRef = useRef<string | null>(null);

  const refresh = useCallback(() => {
    void load()
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load sessions."))
      .finally(() => setLoading(false));
  }, [load]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    api
      .getCatalog()
      .then(setProviders)
      .catch(() => {});
  }, []);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(timer);
  }, []);

  const rowButton = useCallback((id: string) => {
    const buttons = listRef.current?.querySelectorAll<HTMLButtonElement>("[data-session-id]");
    if (!buttons) return null;
    for (const button of buttons) {
      if (button.dataset.sessionId === id) return button;
    }
    return null;
  }, []);

  const focusRow = useCallback(
    (id: string) => {
      setFocusedId(id);
      rowButton(id)?.focus();
    },
    [rowButton]
  );

  // Runs whenever the editor closes. Reading focus from a ref rather than
  // state keeps it out of the render it is reacting to.
  useEffect(() => {
    if (editingId !== null) return;
    const target = restoreFocusRef.current;
    if (!target) return;
    restoreFocusRef.current = null;
    rowButton(target)?.focus();
  }, [editingId, rowButton]);

  // A display name needs the catalog; a model that is not in it falls back to
  // the id the session already stores.
  const modelNames = new Map<string, string>();
  for (const provider of providers) {
    for (const model of provider.models) {
      modelNames.set(`${provider.id}:${model.id}`, model.name);
    }
  }
  const modelLabel = (providerId: string, modelId: string) =>
    modelNames.get(`${providerId}:${modelId}`) ?? modelId;

  const query = searchQuery.trim().toLowerCase();
  const isFiltering = query.length > 0;
  const visible = isFiltering
    ? sessions.filter(
        (session) =>
          session.title.toLowerCase().includes(query) ||
          modelLabel(session.model.provider_id, session.model.model_id)
            .toLowerCase()
            .includes(query)
      )
    : sessions;
  const visibleIds = visible.map((session) => session.id);
  // A filtered list is flat: bucketing it would scatter the matches the user
  // is looking for across headings.
  const groups = isFiltering ? [] : groupByRecency(visible, now);

  // Exactly one row is reachable by Tab: the row that last had focus if it is
  // still visible, else the active session, else the first row.
  const tabbableId = visibleIds.includes(focusedId ?? "")
    ? focusedId
    : visibleIds.includes(activeId ?? "")
      ? activeId
      : visibleIds[0];

  const onRowKeyDown = (event: KeyboardEvent<HTMLButtonElement>, id: string) => {
    const index = visibleIds.indexOf(id);
    let target: string | undefined;
    switch (event.key) {
      case "ArrowDown":
        target = visibleIds[index + 1];
        break;
      case "ArrowUp":
        target = visibleIds[index - 1];
        break;
      case "Home":
        target = visibleIds[0];
        break;
      case "End":
        target = visibleIds[visibleIds.length - 1];
        break;
      default:
        return;
    }
    if (!target) return;
    event.preventDefault();
    focusRow(target);
  };

  const startRename = (session: Session) => {
    setEditingId(session.id);
    setEditTitle(session.title);
    setOriginalTitle(session.title);
  };

  const closeRename = (id: string) => {
    restoreFocusRef.current = id;
    setEditingId(null);
  };

  const commitRename = async (session: Session) => {
    const title = editTitle.trim();
    closeRename(session.id);
    if (!title || title === originalTitle) return;
    try {
      await api.renameSession(session.id, title);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to rename the session.");
    }
  };

  // Errors from a failed import belong to the dialog, not to the list: the
  // dialog stays open on failure and shows the backend's message there.
  const onCreate = (source: ProjectSource) => create(undefined, source);

  const openNewSession = () => setNewSession(true);

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

  const download = (data: unknown, filename: string) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  // Same JSON as before, either the whole list or the one session the menu
  // belongs to.
  const exportAll = () =>
    download(sessions, `vibe-sessions-${new Date().toISOString().split("T")[0]}.json`);
  const exportSession = (session: Session) => download(session, `vibe-session-${session.id}.json`);

  const renderRow = (session: Session) => {
    const isActive = session.id === activeId;
    const isEditing = editingId === session.id;
    const model = modelLabel(session.model.provider_id, session.model.model_id);
    return (
      <li
        key={session.id}
        className={["session-row", isActive ? "session-row-active" : ""].filter(Boolean).join(" ")}
      >
        {isEditing ? (
          // The editor replaces the row button: an input inside a button is
          // invalid, and the row must not stay selectable mid-rename.
          <div className="session-edit">
            <label className="sr-only" htmlFor={`rename-${session.id}`}>
              Session title
            </label>
            <input
              id={`rename-${session.id}`}
              className="session-edit-input"
              value={editTitle}
              autoFocus
              onChange={(event) => setEditTitle(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void commitRename(session);
                } else if (event.key === "Escape") {
                  event.preventDefault();
                  closeRename(session.id);
                }
              }}
            />
            <div className="session-edit-actions">
              <Button variant="primary" size="sm" onClick={() => void commitRename(session)}>
                Save
              </Button>
              <Button variant="ghost" size="sm" onClick={() => closeRename(session.id)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <>
            <button
              type="button"
              className="session-select"
              data-session-id={session.id}
              aria-current={isActive ? "true" : undefined}
              tabIndex={session.id === tabbableId ? 0 : -1}
              onClick={() => {
                focusRow(session.id);
                select(session.id);
              }}
              onKeyDown={(event) => onRowKeyDown(event, session.id)}
            >
              <span className="session-name" title={session.title}>
                {session.title}
              </span>
              {/* updated_at is optional until the backend returns it. */}
              <span className="session-meta">
                {session.updated_at ? (
                  <span
                    className="session-time tnum"
                    title={new Date(session.updated_at).toLocaleString()}
                  >
                    {formatRelativeTime(session.updated_at, now)}
                  </span>
                ) : null}
                <span className="session-model">{model}</span>
              </span>
            </button>
            <Menu
              className="session-actions"
              label={`Session actions for ${session.title}`}
              icon={<Icon name="more" />}
              entries={[
                {
                  id: "rename",
                  label: "Rename",
                  icon: <Icon name="edit" size={14} />,
                  onSelect: () => startRename(session),
                },
                {
                  id: "export",
                  label: "Export",
                  icon: <Icon name="download" size={14} />,
                  onSelect: () => exportSession(session),
                },
                { id: "separator", separator: true },
                {
                  id: "delete",
                  label: "Delete",
                  icon: <Icon name="trash" size={14} />,
                  danger: true,
                  onSelect: () => setConfirmDelete(session),
                },
              ]}
            />
          </>
        )}
      </li>
    );
  };

  const resultsLabel = isFiltering
    ? `${visible.length} ${visible.length === 1 ? "result" : "results"}`
    : "";

  return (
    <div className="panel sessions-panel">
      <div className="panel-header">
        <h2 className="panel-title">Sessions</h2>
        <span className="sessions-count tnum">{sessions.length}</span>
        <div className="panel-header-spacer" />
        <div className="panel-actions">
          <Button variant="primary" size="sm" onClick={openNewSession}>
            New session
          </Button>
        </div>
      </div>

      <div className="panel-body" data-direction="column">
        <div className="toolbar sessions-toolbar">
          <SearchField
            value={searchQuery}
            onValueChange={setSearchQuery}
            label="Search sessions"
            placeholder="Search by title or model…"
          />
          {/* The list-level export lives here rather than in the 40px header:
              it names its scope, and the header only has room for the count
              and the primary action at 260px. */}
          <Button variant="ghost" size="sm" onClick={exportAll} disabled={sessions.length === 0}>
            Export all
          </Button>
        </div>

        {error ? (
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
        ) : null}

        {/* Always mounted so the region exists before its text changes; empty
            text means "no filter", which is not an announcement. */}
        <p className="sessions-results" aria-live="polite">
          {resultsLabel}
        </p>

        <nav ref={listRef} className="sessions-list scroll-region" aria-label="Sessions">
          {loading ? (
            <div className="sessions-loading">
              <Spinner size="sm" label="Loading sessions" />
            </div>
          ) : error ? null : visible.length === 0 ? (
            isFiltering ? (
              // Quieter than the first-run state: no icon and no call to
              // action, just the way back to the full list.
              <EmptyState
                headingLevel="h3"
                title="No sessions match"
                body={`Nothing matches "${searchQuery.trim()}".`}
                action={
                  <Button variant="ghost" size="sm" onClick={() => setSearchQuery("")}>
                    Clear search
                  </Button>
                }
              />
            ) : (
              <EmptyState
                headingLevel="h3"
                icon={<Icon name="chat" size={20} />}
                title="No sessions yet"
                body="Start a new session and describe the app you want to build."
                action={
                  <Button variant="primary" size="sm" onClick={openNewSession}>
                    New session
                  </Button>
                }
              />
            )
          ) : isFiltering ? (
            <ul className="session-items">{visible.map(renderRow)}</ul>
          ) : (
            groups.map((group) => (
              <section
                key={group.id}
                className="session-group"
                aria-labelledby={`sessions-${group.id}`}
              >
                <h3 className="section-label" id={`sessions-${group.id}`}>
                  {group.label}
                </h3>
                <ul className="session-items">{group.sessions.map(renderRow)}</ul>
              </section>
            ))
          )}
        </nav>
      </div>

      <NewSessionDialog
        open={newSession}
        onClose={() => setNewSession(false)}
        onCreate={onCreate}
      />

      <ConfirmDialog
        open={!!confirmDelete}
        onClose={() => setConfirmDelete(null)}
        onConfirm={doDelete}
        title={confirmDelete ? `Delete "${confirmDelete.title}"?` : "Delete session?"}
        body="This permanently removes the session and its history."
        confirmLabel="Delete"
      />
    </div>
  );
}
