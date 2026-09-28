// apps/vibe/src/features/sessions/SessionsPanel.tsx
import { useSessionsStore } from "./store";

export function SessionsPanel() {
  const { sessions, activeId, load, create, remove, select } = useSessionsStore();
  return (
    <div style={{ width: 240, borderRight: "1px solid #ccc", display: "flex", flexDirection: "column" }}>
      <button onClick={() => create()} style={{ margin: 8 }}>New</button>
      <div style={{ flex: 1, overflow: "auto" }}>
        {sessions.map((s) => (
          <div
            key={s.id}
            onClick={() => select(s.id)}
            style={{ padding: 8, cursor: "pointer", background: s.id === activeId ? "#eee" : "none" }}
          >
            {s.title}
            <button onClick={(e) => { e.stopPropagation(); remove(s.id); }}>×</button>
          </div>
        ))}
      </div>
    </div>
  );
}
