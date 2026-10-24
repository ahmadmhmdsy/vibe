// apps/vibe/src/features/vcs/SourceControlPanel.tsx
//
// Source control for the session's workspace (M8/C2). Three states, and the
// first one is the common one for a generated app: not a repository yet.
//
// Nothing here pushes. A remote is the user's own terminal business, so the
// panel stops at commit, branch, and diff.
import { useEffect, useState } from "react";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { IconButton } from "../../components/ui/IconButton";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { useToast } from "../../components/ui";
import { Icon } from "../../components/icons/Icon";
import { formatRelativeTime } from "../../lib/format";
import { usePolling } from "../../hooks/usePolling";
import { emptyVcsView, useVcsStore } from "./store";
import "./vcs.css";

/** Porcelain codes, said in words. `?` is better as "New" than as "??". */
const STATUS_LABELS: Record<string, string> = {
  "??": "New",
  M: "Modified",
  A: "Added",
  D: "Deleted",
  R: "Renamed",
  C: "Copied",
  U: "Conflict",
};

function statusLabel(code: string): string {
  // Column 1 is the index, column 2 the worktree; either one being set is what
  // matters for a one-word label.
  for (const ch of code) {
    const label = STATUS_LABELS[ch];
    if (label) return label;
  }
  return "Changed";
}

function splitPath(path: string): { dir: string; name: string } {
  const at = path.lastIndexOf("/");
  return at === -1
    ? { dir: "", name: path }
    : { dir: path.slice(0, at + 1), name: path.slice(at + 1) };
}

export function SourceControlPanel({ sessionId, active }: { sessionId: string; active: boolean }) {
  const view = useVcsStore((s) => s.bySession[sessionId]) ?? emptyVcsView;
  const load = useVcsStore((s) => s.load);
  const select = useVcsStore((s) => s.select);
  const commit = useVcsStore((s) => s.commit);
  const init = useVcsStore((s) => s.init);
  const branch = useVcsStore((s) => s.branch);
  const { toast } = useToast();

  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [branchOpen, setBranchOpen] = useState(false);
  const [branchName, setBranchName] = useState("");
  const [branchError, setBranchError] = useState<string | null>(null);

  const isRepo = view.status?.is_repo ?? false;

  useEffect(() => {
    if (active) void load(sessionId);
  }, [active, sessionId, load]);

  // The agent writes files throughout a turn, so a panel that only refreshed on
  // open would show a stale change list for the whole build.
  usePolling(() => load(sessionId, { quiet: true }), {
    interval: 5000,
    // Not while a diff is open: a refresh would re-read it under the pointer,
    // and nothing the agent writes is visible in that view anyway.
    enabled: active && isRepo && !view.diff,
  });

  const doCommit = async () => {
    const text = message.trim();
    if (!text) return;
    setBusy(true);
    try {
      const committed = await commit(sessionId, text);
      if (committed) {
        setMessage("");
        toast("Committed", "success");
      } else {
        // Not an error: the workspace was already clean.
        toast("Nothing to commit — the workspace has not changed.", "info");
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : "Commit failed.", "error");
    } finally {
      setBusy(false);
    }
  };

  const doInit = async () => {
    setBusy(true);
    try {
      await init(sessionId);
      toast("Repository created", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not create the repository.", "error");
    } finally {
      setBusy(false);
    }
  };

  const doBranch = async () => {
    const name = branchName.trim();
    if (!name) return;
    setBusy(true);
    setBranchError(null);
    try {
      await branch(sessionId, name, true);
      setBranchOpen(false);
      setBranchName("");
      toast(`On branch ${name}`, "success");
    } catch (e) {
      // The dialog stays open: a rejected name is nearly always a typo, and the
      // message from git says which rule it broke.
      setBranchError(e instanceof Error ? e.message : "Could not create the branch.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel vcs-panel">
      <div className="panel-header">
        <h2 className="panel-title">Source control</h2>
        {view.status?.branch ? (
          <span className="vcs-branch">
            <Icon name="branch" size={12} />
            {view.status.branch}
          </span>
        ) : null}
        <div className="panel-header-spacer" />
        <div className="panel-actions">
          <IconButton label="Refresh changes" onClick={() => void load(sessionId)}>
            <Icon name="retry" size={14} />
          </IconButton>
          <Button variant="ghost" size="sm" disabled={!isRepo} onClick={() => setBranchOpen(true)}>
            New branch
          </Button>
        </div>
      </div>

      <div className="panel-body" data-direction="column">
        {view.error ? (
          <div className="vcs-alert">
            <ErrorBanner message={view.error} onRetry={() => void load(sessionId)} />
          </div>
        ) : null}

        {view.loading && !view.status ? (
          <div className="vcs-loading">
            <Spinner size="sm" label="Reading the repository" />
          </div>
        ) : null}

        {view.status && !view.status.is_repo ? (
          <EmptyState
            headingLevel="h3"
            icon={<Icon name="branch" size={20} />}
            title="This workspace is not a Git repository"
            body="Create one to track what the agent writes, review a change, and commit it."
            action={
              <Button variant="primary" size="sm" loading={busy} onClick={() => void doInit()}>
                Create repository
              </Button>
            }
          />
        ) : null}

        {isRepo && view.diff ? (
          <div className="vcs-diff-view">
            <div className="vcs-diff-head">
              <Button variant="ghost" size="sm" onClick={() => void select(sessionId, null)}>
                <Icon name="arrowLeft" size={14} /> All changes
              </Button>
              <span className="vcs-diff-path" title={view.diff.path}>
                {splitPath(view.diff.path).name}
              </span>
            </div>
            {view.diff.text ? (
              <>
                {view.diff.truncated ? (
                  <p className="vcs-diff-note">Showing the first part of a large change.</p>
                ) : null}
                <pre className="vcs-diff scroll-region">{view.diff.text}</pre>
              </>
            ) : (
              // git has nothing to show for a path it does not track yet, and
              // an empty box would read as a bug.
              <p className="vcs-diff-note">
                No diff yet: this file is new. It is committed in full.
              </p>
            )}
          </div>
        ) : null}

        {isRepo && !view.diff ? (
          <>
            <div className="vcs-changes scroll-region" role="list" aria-label="Changed files">
              {view.status?.files.length ? (
                view.status.files.map((file) => (
                  <button
                    type="button"
                    role="listitem"
                    key={file.path}
                    className="vcs-change"
                    onClick={() => void select(sessionId, file)}
                  >
                    <span className={`vcs-change-code vcs-code-${file.status[0].trim() || "w"}`}>
                      {statusLabel(file.status)}
                    </span>
                    <span className="vcs-change-path">
                      <span className="vcs-change-dir">{splitPath(file.path).dir}</span>
                      {splitPath(file.path).name}
                    </span>
                  </button>
                ))
              ) : (
                <p className="vcs-clean">No changes. The workspace matches the last commit.</p>
              )}
            </div>

            <form
              className="vcs-commit"
              onSubmit={(e) => {
                e.preventDefault();
                void doCommit();
              }}
            >
              <label className="field-label" htmlFor="vcs-message">
                Commit message
              </label>
              <input
                id="vcs-message"
                value={message}
                placeholder="Describe this change"
                autoComplete="off"
                onChange={(e) => setMessage(e.target.value)}
              />
              <Button
                variant="primary"
                size="sm"
                type="submit"
                disabled={!message.trim() || !view.status?.files.length}
                loading={busy}
              >
                Commit {view.status?.files.length ? `(${view.status.files.length})` : ""}
              </Button>
            </form>

            <div className="vcs-log">
              <h3 className="section-label">Recent commits</h3>
              {view.log.length ? (
                <ul className="vcs-log-list">
                  {view.log.slice(0, 10).map((c) => (
                    <li key={c.sha} className="vcs-log-entry">
                      <code className="vcs-sha">{c.sha.slice(0, 7)}</code>
                      <span className="vcs-log-subject" title={c.subject}>
                        {c.subject}
                      </span>
                      <span className="vcs-log-date">{formatRelativeTime(c.date)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="vcs-clean">No commits yet.</p>
              )}
            </div>
          </>
        ) : null}
      </div>

      <Modal
        open={branchOpen}
        onClose={() => {
          setBranchOpen(false);
          setBranchError(null);
        }}
        title="New branch"
      >
        <form
          className="vcs-branch-form"
          onSubmit={(e) => {
            e.preventDefault();
            void doBranch();
          }}
        >
          <div className="field">
            <label className="field-label" htmlFor="vcs-branch-name">
              Branch name
            </label>
            <input
              id="vcs-branch-name"
              value={branchName}
              autoComplete="off"
              placeholder="feature/new-thing"
              onChange={(e) => setBranchName(e.target.value)}
            />
            <p className="field-hint">
              Created from the current branch and switched to. Nothing is pushed.
            </p>
          </div>
          {branchError ? <ErrorBanner message={branchError} /> : null}
          <div className="confirm-actions">
            <Button variant="secondary" type="button" onClick={() => setBranchOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" disabled={!branchName.trim()} loading={busy}>
              Create branch
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
