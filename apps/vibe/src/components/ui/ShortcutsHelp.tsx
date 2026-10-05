// components/ui/ShortcutsHelp.tsx — Keyboard shortcuts help modal.
// Press ? to open.

import { Modal } from "./Modal";

interface ShortcutsHelpProps {
  open: boolean;
  onClose: () => void;
}

const SHORTCUTS = [
  { keys: ["Cmd", ","], description: "Toggle settings" },
  { keys: ["Cmd", "K"], description: "Open command palette" },
  { keys: ["?"], description: "Show this help" },
  { keys: ["Esc"], description: "Close dialog" },
  { keys: ["Enter"], description: "Send message" },
  { keys: ["Shift", "Enter"], description: "New line in message" },
];

export function ShortcutsHelp({ open, onClose }: ShortcutsHelpProps) {
  return (
    <Modal open={open} onClose={onClose} title="Keyboard shortcuts">
      <div className="shortcuts-list">
        {SHORTCUTS.map((s, i) => (
          <div key={i} className="shortcut-row">
            <span className="shortcut-keys">
              {s.keys.map((k, j) => (
                <span key={j}>
                  {j > 0 && <span className="shortcut-plus">+</span>}
                  <kbd className="shortcut-key">{k}</kbd>
                </span>
              ))}
            </span>
            <span className="shortcut-description">{s.description}</span>
          </div>
        ))}
      </div>
    </Modal>
  );
}
