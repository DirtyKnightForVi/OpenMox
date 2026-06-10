"use client";

import { useTheme } from "next-themes";
import { Sun, Moon, Monitor } from "@phosphor-icons/react";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <button className="p-1.5 rounded-lg text-text-muted hover:bg-surface-tertiary transition-colors" aria-label="Toggle theme">
        <Monitor size={16} />
      </button>
    );
  }

  const next = theme === "system" ? "light" : theme === "light" ? "dark" : "system";
  const label = theme === "system" ? "System" : theme === "light" ? "Light" : "Dark";

  return (
    <button
      onClick={() => setTheme(next)}
      className="p-1.5 rounded-lg text-text-muted hover:bg-surface-tertiary transition-colors"
      title={`Current: ${label}. Click to switch.`}
      aria-label={`Current theme: ${label}`}
    >
      {resolvedTheme === "dark" ? (
        <Moon size={16} weight="fill" />
      ) : resolvedTheme === "light" ? (
        <Sun size={16} weight="fill" />
      ) : (
        <Monitor size={16} />
      )}
    </button>
  );
}
