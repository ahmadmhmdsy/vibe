// apps/vibe/src/features/code/CodePanel.tsx
import { useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import { useCodeStore } from "./store";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";
import { detectLanguage } from "../../lib/format";
import "./code.css";

type SaveState = "idle" | "saving" | "saved";

export function CodePanel({ sessionId }: { sessionId: string }) {
  const { files, selectedFile, contents, setSelectedFile, loadFiles, loadFile, saveFile } = useCodeStore();
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");

  // Refresh the file list (picks up agent-written files).
  useEffect(() => {
    loadFiles(sessionId).finally(() => setLoading(false));
    const t = setInterval(() => loadFiles(sessionId), 3000);
    return () => clearInterval(t);
  }, [sessionId]);

  // Load the selected file's content.
  useEffect(() => {
    if (selectedFile) loadFile(sessionId, selectedFile);
  }, [selectedFile, sessionId]);

  const onEdit = (value: string | undefined) => {
    if (!selectedFile || value === undefined) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      setSaveError(null);
      setSaveState("saving");
      saveFile(sessionId, selectedFile, value)
        .then(() => setSaveState("saved"))
        .catch((e) => {
          setSaveState("idle");
          setSaveError(e instanceof Error ? `Save failed: ${e.message}` : "Save failed.");
        });
    }, 800);
  };

  return (
    <div className="panel-code code-panel">
      <div className="code-file-list">
        {loading && files.length === 0 ? (
          <div className="code-loading">
            <Spinner size="sm" label="Loading files" />
          </div>
        ) : files.length === 0 ? (
          <EmptyState
            title="No files yet"
            body="The agent has not written any files for this session."
          />
        ) : (
          files.map((f) => (
            <button
              key={f}
              className={f === selectedFile ? "code-file code-file-active" : "code-file"}
              aria-pressed={f === selectedFile}
              onClick={() => setSelectedFile(f)}
            >
              {f}
            </button>
          ))
        )}
      </div>
      <div className="code-editor">
        <div className="code-save-status" role="status" aria-live="polite">
          {saveState === "saving" && <span className="muted">Saving...</span>}
          {saveState === "saved" && <span className="muted">Saved</span>}
        </div>
        {saveError && (
          <div className="code-save-error" role="alert">
            {saveError}
          </div>
        )}
        {selectedFile && (
          <Editor
            path={selectedFile}
            language={detectLanguage(selectedFile)}
            value={contents[selectedFile] ?? ""}
            onChange={onEdit}
          />
        )}
      </div>
    </div>
  );
}
