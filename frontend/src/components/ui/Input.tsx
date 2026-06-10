import { forwardRef, type InputHTMLAttributes } from "react";
import { clsx } from "clsx";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, id, ...props }, ref) => (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={id} className="text-xs font-medium text-text-secondary block">
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={id}
        className={clsx(
          "w-full px-3 py-2 text-sm rounded-lg border transition-colors",
          "bg-surface text-text-primary placeholder:text-text-muted",
          "focus:outline-none focus:ring-2 focus:ring-accent-ring focus:border-accent",
          error ? "border-red-400" : "border-border hover:border-accent/40",
          className,
        )}
        {...props}
      />
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  ),
);
Input.displayName = "Input";
