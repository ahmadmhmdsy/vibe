// components/ui/StatusDot.tsx — colour plus a text label, never colour alone.
//
// The visible dot carries no accessible name of its own: the label is always
// rendered, either inline by the caller or as visually-hidden text here. That
// is the rule that keeps a red/green-only signal from being unreadable.

export type StatusKind = "idle" | "running" | "ok" | "warning" | "error";

export interface StatusDotProps {
  status: StatusKind;
  /** Accessible text. Visually hidden unless `showLabel` is set. */
  label: string;
  showLabel?: boolean;
  className?: string;
}

export function StatusDot({ status, label, showLabel = false, className }: StatusDotProps) {
  return (
    <span className={["status-dot-wrap", className].filter(Boolean).join(" ")}>
      <span className="status-dot" data-status={status} aria-hidden="true" />
      <span className={showLabel ? "status-dot-label" : "sr-only"}>{label}</span>
    </span>
  );
}
