// components/ui/ShortcutsHelp.tsx — the keyboard reference, opened with "?".
//
// Every row here mirrors a binding App.tsx actually installs, and the primary
// modifier is spelled per platform: a Windows user told to press "Cmd ," would
// never find the shortcut.

import { Modal } from "./Modal";
import { Kbd } from "./Kbd";
import { isMacPlatform } from "../../lib/platform";

interface ShortcutsHelpProps {
  open: boolean;
  onClose: () => void;
}

interface Shortcut {
  keys: string[];
  description: string;
}

export function ShortcutsHelp({ open, onClose }: ShortcutsHelpProps) {
  const isMac = isMacPlatform();
  const primary = isMac ? "Cmd" : "Ctrl";

  const shortcuts: Shortcut[] = [
    { keys: [primary, ","], description: "Open settings" },
    { keys: [primary, "K"], description: "Open the command palette" },
    { keys: [primary, "B"], description: "Show or hide the sessions sidebar" },
    { keys: [primary, "J"], description: "Show or hide the preview and code panel" },
    // Ctrl+N and Ctrl+Shift+N are reserved by the browser on Windows and Linux,
    // so those platforms get Ctrl+Alt+N instead. Matches App.tsx exactly.
    { keys: isMac ? [primary, "N"] : [primary, "Alt", "N"], description: "Start a new session" },
    { keys: ["?"], description: "Show this reference" },
    { keys: ["Esc"], description: "Close a dialog, or an open drawer" },
    { keys: ["Enter"], description: "Send the message" },
    { keys: ["Shift", "Enter"], description: "Insert a new line" },
  ];

  return (
    <Modal open={open} onClose={onClose} title="Keyboard shortcuts">
      <div className="shortcuts-list">
        {shortcuts.map((shortcut) => (
          <div key={shortcut.description} className="shortcut-row">
            <span className="shortcut-keys">
              <Kbd keys={shortcut.keys} />
            </span>
            <span className="shortcut-description">{shortcut.description}</span>
          </div>
        ))}
      </div>
    </Modal>
  );
}
