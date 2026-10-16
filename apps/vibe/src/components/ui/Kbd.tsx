// components/ui/Kbd.tsx — renders a keyboard chord as individual keys.
export interface KbdProps {
  /** One entry per key, e.g. ["Ctrl", "K"]. */
  keys: readonly string[];
  className?: string;
}

export function Kbd({ keys, className }: KbdProps) {
  return (
    <span className={["kbd-group", className].filter(Boolean).join(" ")}>
      {keys.map((key, index) => (
        <span key={`${key}-${index}`} className="kbd-group">
          {index > 0 ? (
            <span className="kbd-sep" aria-hidden="true">
              +
            </span>
          ) : null}
          <kbd className="kbd">{key}</kbd>
        </span>
      ))}
    </span>
  );
}
