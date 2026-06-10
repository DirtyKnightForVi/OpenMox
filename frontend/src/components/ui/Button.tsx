import { type ButtonHTMLAttributes, forwardRef } from "react";
import { clsx } from "clsx";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", children, ...props }, ref) => (
    <button
      ref={ref}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all",
        "active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none",
        {
          primary:
            "bg-accent text-white hover:bg-accent-hover shadow-xs",
          secondary:
            "border border-border bg-surface hover:bg-surface-tertiary text-text-primary",
          ghost:
            "text-text-secondary hover:bg-surface-tertiary hover:text-text-primary",
          danger:
            "bg-red-500 text-white hover:bg-red-600",
        }[variant],
        {
          sm: "px-2.5 py-1 text-xs",
          md: "px-3.5 py-2 text-sm",
          lg: "px-5 py-2.5 text-base",
        }[size],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  ),
);
Button.displayName = "Button";
