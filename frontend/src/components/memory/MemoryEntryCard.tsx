"use client";

import { PushPin } from "@phosphor-icons/react";
import { clsx } from "clsx";
import type { MemoryEntry } from "@/lib/types";

const ENTRY_TYPE_STYLES: Record<string, { label: string; className: string }> = {
  fact: { label: "Fact", className: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300" },
  decision: { label: "Decision", className: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" },
  reflection: { label: "Reflection", className: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300" },
  shendu: { label: "慎独", className: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300" },
  preference: { label: "Preference", className: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300" },
  context: { label: "Context", className: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400" },
};

interface MemoryEntryCardProps {
  entry: MemoryEntry;
  onPin?: (entry: MemoryEntry) => void;
  onEdit?: (entry: MemoryEntry) => void;
  onDelete?: (entry: MemoryEntry) => void;
}

export function MemoryEntryCard({ entry, onPin, onEdit, onDelete }: MemoryEntryCardProps) {
  const typeStyle = ENTRY_TYPE_STYLES[entry.type] || ENTRY_TYPE_STYLES.context;

  return (
    <div className="bg-surface rounded-lg border border-border p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm leading-relaxed flex-1 text-text-primary">{entry.content}</p>
        <div className="flex items-center gap-1 shrink-0">
          {onPin && (
            <button
              onClick={() => onPin(entry)}
              className={clsx(
                "p-1 rounded transition-colors",
                entry.pinned ? "text-amber-500" : "text-text-muted hover:text-text-secondary",
              )}
              aria-label={entry.pinned ? "Unpin" : "Pin"}
            >
              <PushPin size={14} weight={entry.pinned ? "fill" : "regular"} />
            </button>
          )}
          {onEdit && (
            <button
              onClick={() => onEdit(entry)}
              className="p-1 text-text-muted hover:text-text-secondary rounded transition-colors"
              aria-label="Edit"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M17 3a2.85 2.85 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
              </svg>
            </button>
          )}
          {onDelete && (
            <button
              onClick={() => onDelete(entry)}
              className="p-1 text-text-muted hover:text-red-500 rounded transition-colors"
              aria-label="Delete"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M3 6h18M8 6V4a1 1 0 011-1h6a1 1 0 011 1v2M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6" />
              </svg>
            </button>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 mt-1.5">
        <span className={clsx("text-[10px] px-1.5 py-0.5 rounded font-medium", typeStyle.className)}>
          {typeStyle.label}
        </span>
        {entry.importance > 0 && (
          <span className="text-[10px] text-text-muted">
            {Math.round(entry.importance * 100)}%
          </span>
        )}
        <span className="text-[10px] text-text-muted ml-auto">
          {new Date(entry.created_at).toLocaleDateString("zh-CN", {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
    </div>
  );
}
