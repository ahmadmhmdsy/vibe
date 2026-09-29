// apps/vibe/src/features/code/CodePanel.tsx
import { useEffect, useRef } from "react";
import Editor from "@monaco-editor/react";
import { useCodeStore } from "./store";

export function CodePanel({ sessionId }: { sessionId: string }) {
  const { files, selectedFile, contents, setSelectedFile, loadFiles, loadFile, saveFile } = useCodeStore();
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Refresh the file list (picks up agent-written files).
  useEffect(() => {
    loadFiles(sessionId);
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
    saveTimer.current = setTimeout(() => saveFile(sessionId, selectedFile, value), 800);
  };

  return (
    <div className="panel-code" style={{ display: "flex", height: "100%" }}>
      <div style={{ width: 200, overflow: "auto", borderRight: "1px solid #ccc" }}>
        {files.map((f) => (
          <div key={f} onClick={() => setSelectedFile(f)}
            style={{ padding: 4, cursor: "pointer", background: f === selectedFile ? "#eee" : "transparent" }}>
            {f}
          </div>
        ))}
      </div>
      <div style={{ flex: 1 }}>
        {selectedFile && (
          <Editor
            path={selectedFile}
            language="typescript"
            value={contents[selectedFile] ?? ""}
            onChange={onEdit}
          />
        )}
      </div>
    </div>
  );
}
