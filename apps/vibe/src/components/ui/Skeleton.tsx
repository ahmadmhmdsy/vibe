// components/ui/Skeleton.tsx — a placeholder that holds the final layout.
export interface SkeletonProps {
  /** CSS length. Defaults to 100%. */
  width?: string | number;
  /** CSS length. Defaults to 1em. */
  height?: string | number;
  radius?: string;
  className?: string;
}

export function Skeleton({ width = "100%", height = "1em", radius, className }: SkeletonProps) {
  return (
    <span
      className={["skeleton", className].filter(Boolean).join(" ")}
      aria-hidden="true"
      style={{ width, height, borderRadius: radius }}
    />
  );
}
