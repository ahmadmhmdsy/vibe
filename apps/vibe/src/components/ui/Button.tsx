// components/ui/Button.tsx — Button component with variants and loading state.

import { forwardRef, memo, type ButtonHTMLAttributes } from "react";
import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

export const Button = memo(
  forwardRef<HTMLButtonElement, ButtonProps>(function Button(
    { variant = "secondary", size = "md", loading = false, disabled, children, className, ...rest },
    ref
  ) {
    const classes = ["btn", `btn-${variant}`, `btn-${size}`, className].filter(Boolean).join(" ");
    return (
      <button ref={ref} className={classes} disabled={disabled || loading} {...rest}>
        {loading && <Spinner size="sm" />}
        {children}
      </button>
    );
  })
);
