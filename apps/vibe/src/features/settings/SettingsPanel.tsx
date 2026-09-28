// apps/vibe/src/features/settings/SettingsPanel.tsx
import { useSettingsStore } from "./store";

export function SettingsPanel() {
  const { providers } = useSettingsStore();
  return (
    <div style={{ padding: 8 }}>
      <h2>Settings</h2>
      {providers.length === 0 ? (
        <p>No providers loaded</p>
      ) : (
        <ul>
          {providers.map((p) => (
            <li key={p.id}>{p.name}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
