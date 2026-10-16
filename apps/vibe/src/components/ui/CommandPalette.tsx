// components/ui/CommandPalette.tsx — Command palette for quick actions.
// Press Cmd+K to open.

import { useState, useEffect, useRef } from "react";
import { Modal } from "./Modal";

interface Command {
  id: string;
  title: string;
  description?: string;
  action: () => void;
  shortcut?: string[];
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  commands: Command[];
}

export function CommandPalette({ open, onClose, commands }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const [prevOpen, setPrevOpen] = useState(open);

  // Reset the query and selection each time the palette opens. Done during
  // render (not in an effect) so the first paint of an open palette is already
  // clean — an effect would flash the previous query for one frame.
  if (prevOpen !== open) {
    setPrevOpen(open);
    if (open) {
      setQuery("");
      setSelectedIndex(0);
    }
  }

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const filtered = commands.filter(
    (c) =>
      c.title.toLowerCase().includes(query.toLowerCase()) ||
      c.description?.toLowerCase().includes(query.toLowerCase())
  );

  const execute = (command: Command) => {
    command.action();
    onClose();
  };

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
    // Reset the selection when the query changes so the first match is always
    // highlighted. Done in the event handler, not an effect.
    setSelectedIndex(0);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && filtered[selectedIndex]) {
      e.preventDefault();
      execute(filtered[selectedIndex]);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Command palette">
      <div className="command-palette">
        <input
          ref={inputRef}
          className="command-palette-input"
          placeholder="Type a command..."
          value={query}
          onChange={onInputChange}
          onKeyDown={onKeyDown}
          aria-label="Search commands"
        />
        <div className="command-palette-list" role="listbox">
          {filtered.length === 0 ? (
            <div className="command-palette-empty">No commands found</div>
          ) : (
            filtered.map((c, i) => (
              <button
                key={c.id}
                className={
                  i === selectedIndex ? "command-item command-item-active" : "command-item"
                }
                onClick={() => execute(c)}
                onMouseEnter={() => setSelectedIndex(i)}
                role="option"
                aria-selected={i === selectedIndex}
              >
                <span className="command-item-title">{c.title}</span>
                {c.description && <span className="command-item-description">{c.description}</span>}
                {c.shortcut && (
                  <span className="command-item-shortcut">{c.shortcut.join(" ")}</span>
                )}
              </button>
            ))
          )}
        </div>
      </div>
    </Modal>
  );
}
