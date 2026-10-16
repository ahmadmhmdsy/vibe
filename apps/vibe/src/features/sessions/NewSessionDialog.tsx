// apps/vibe/src/features/sessions/NewSessionDialog.tsx
// Choose where a new session's workspace comes from (M8/C1).
//
// Four kinds, one control. A folder on the server's filesystem is a path the
// user types: the browser cannot pick a directory the backend can read, and
// pretending otherwise would hand the agent a path it cannot open. The path
// field says which machine it is relative to so that is not a surprise.
import { useState, type FormEvent } from "react";
import { Button } from "../../components/ui/Button";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { Modal } from "../../components/ui/Modal";
import type { ProjectSource } from "../../lib/api";

interface Choice {
  kind: ProjectSource["kind"];
  label: string;
  hint: string;
}

const CHOICES: Choice[] = [
  {
    kind: "empty",
    label: "Empty workspace",
    hint: "Start from nothing. The agent writes every file.",
  },
  {
    kind: "template",
    label: "New React app",
    hint: "A Vite + React + TypeScript project, ready to install and run.",
  },
  {
    kind: "folder",
    label: "Import a folder",
    hint: "Opens a project already on this machine, in place.",
  },
  {
    kind: "git",
    label: "Clone a repository",
    hint: "Clones a Git URL into the workspace. Requires git.",
  },
];

export function NewSessionDialog({
  open,
  onClose,
  onCreate,
}: {
  open: boolean;
  onClose: () => void;
  /** Rejects with the backend's message; the dialog stays open so it can be read. */
  onCreate: (source: ProjectSource) => Promise<unknown>;
}) {
  const [kind, setKind] = useState<ProjectSource["kind"]>("empty");
  const [path, setPath] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const source: ProjectSource =
    kind === "folder"
      ? { kind: "folder", path: path.trim() }
      : kind === "git"
        ? { kind: "git", url: url.trim() }
        : { kind };
  // The backend owns the rule (a folder kind needs a path); this only keeps the
  // button from sending a request that is certain to fail.
  const ready = kind === "folder" ? path.trim() !== "" : kind === "git" ? url.trim() !== "" : true;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onCreate(source);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create the session.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="New session">
      <form className="new-session-form" onSubmit={submit}>
        <fieldset className="new-session-choices">
          <legend className="field-label">Start from</legend>
          {CHOICES.map((choice) => (
            <label key={choice.kind} className="new-session-choice">
              <input
                type="radio"
                name="project-source"
                value={choice.kind}
                checked={kind === choice.kind}
                onChange={() => setKind(choice.kind)}
              />
              <span className="new-session-choice-text">
                <span className="new-session-choice-label">{choice.label}</span>
                <span className="new-session-choice-hint">{choice.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>

        {kind === "folder" ? (
          <div className="field">
            <label className="field-label" htmlFor="new-session-folder">
              Folder path on the machine running vibe
            </label>
            <input
              id="new-session-folder"
              value={path}
              autoComplete="off"
              placeholder="C:\projects\my-app"
              onChange={(event) => setPath(event.target.value)}
            />
            <p className="field-hint">
              Opened where it is: nothing is copied, moved, or deleted when the session goes away.
            </p>
          </div>
        ) : null}

        {kind === "git" ? (
          <div className="field">
            <label className="field-label" htmlFor="new-session-url">
              Repository URL
            </label>
            <input
              id="new-session-url"
              value={url}
              autoComplete="off"
              placeholder="https://github.com/owner/repo.git"
              onChange={(event) => setUrl(event.target.value)}
            />
            <p className="field-hint">
              Cloned into the workspace. Deleting the session deletes the clone.
            </p>
          </div>
        ) : null}

        {error ? <ErrorBanner message={error} /> : null}

        <div className="confirm-actions">
          <Button variant="secondary" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={!ready || busy}>
            {busy ? "Creating…" : "Create"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
