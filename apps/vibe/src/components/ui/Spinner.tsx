// components/ui/Spinner.tsx — Animated loading spinner.
// Uses CSS variables for sizing and color.

import { memo } from "react";

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  label?: string;
}

const SIZES = { sm: 12, md: 16, lg: 24 } as const;

export const Spinner = memo(function Spinner({ size = "md", label = "Loading" }: SpinnerProps) {
  const px = SIZES[size];
  return (
    <span
      role="status"
      aria-label={label}
      className="spinner"
      style={{
        width: px,
        height: px,
      }}
    />
  );
});
