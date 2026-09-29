// apps/vibe/src/components/ui/Spinner.tsx
interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  label?: string;
}

const SIZES = { sm: 12, md: 16, lg: 24 } as const;

export function Spinner({ size = "md", label = "Loading" }: SpinnerProps) {
  const px = SIZES[size];
  return (
    <span
      role="status"
      aria-label={label}
      style={{
        display: "inline-block",
        width: px,
        height: px,
        border: "2px solid var(--border)",
        borderTopColor: "var(--accent)",
        borderRadius: "50%",
        animation: "vibe-spin 0.7s linear infinite",
        flexShrink: 0,
      }}
    />
  );
}
