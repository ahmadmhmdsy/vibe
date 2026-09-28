// apps/vibe/src/features/code/CodePanel.tsx
import Editor from "@monaco-editor/react";

export function CodePanel({ files, selectedFile }: { files: string[]; selectedFile: string | null }) {
  return (
    <div style={{ display: "flex", height: "100%" }}>
      <div style={{ width: 200, overflow: "auto", borderRight: "1px solid #ccc" }}>
        {files.map((f) => <div key={f} style={{ padding: 4, cursor: "pointer" }}>{f}</div>)}
      </div>
      <div style={{ flex: 1 }}>
        {selectedFile && <Editor path={selectedFile} language="typescript" options={{ readOnly: true }} />}
      </div>
    </div>
  );
}
