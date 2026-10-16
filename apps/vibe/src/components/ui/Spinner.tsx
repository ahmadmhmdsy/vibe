// components/ui/Spinner.tsx — Animated loading spinner.
// Uses CSS variables for sizing and color.

import { memo } from "react";

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  label?: string;
  /** Whether the spinner is its own live region.
   *
   * Default true: a spinner standing alone is the thing that should announce.
   * Set false inside an existing live region (the chat transcript is role="log"),
   * where a nested status region makes screen readers announce the same event
   * twice. */
  live?: boolean;
}

const SIZES = { sm: 12, md: 16, lg: 24 } as const;

export const Spinner = memo(function Spinner({
  size = "md",
  label = "Loading",
  live = true,
}: SpinnerProps) {
  const px = SIZES[size];
  return (
    <span
      role={live ? "status" : undefined}
      aria-label={label}
      className="spinner"
      style={{
        width: px,
        height: px,
      }}
    />
  );
});
