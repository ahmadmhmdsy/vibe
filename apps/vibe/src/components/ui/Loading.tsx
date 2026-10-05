// components/ui/Loading.tsx — Consistent loading indicator.
// Replaces ad-hoc spinners with a unified loading component.

import { Spinner } from "./Spinner";

interface LoadingProps {
  /** Loading message for screen readers */
  label?: string;
  /** Visual size */
  size?: "sm" | "md" | "lg";
  /** Whether to show a full-screen overlay */
  overlay?: boolean;
  /** Additional className */
  className?: string;
}

export function Loading({ label = "Loading", size = "md", overlay = false, className = "" }: LoadingProps) {
  const content = (
    <div className={`loading ${className}`} role="status" aria-label={label}>
      <Spinner size={size} label={label} />
      <span className="loading-text">{label}...</span>
    </div>
  );

  if (overlay) {
    return <div className="loading-overlay">{content}</div>;
  }

  return content;
}
