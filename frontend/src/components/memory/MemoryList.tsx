"use client";

import { useState } from "react";
import { MemoryEntryCard } from "./MemoryEntryCard";
import type { MemoryEntry } from "@/lib/types";

interface MemoryListProps {
  entries: MemoryEntry[];
  title: string;
  emptyMessage?: string;
  onPin?: (entry: MemoryEntry) => void;
  onSaveEdit?: (entry: MemoryEntry, content: string) => void;
  onDelete?: (entry: MemoryEntry) => void;
}

export function MemoryList({ entries, title, emptyMessage, onPin, onSaveEdit, onDelete }: MemoryListProps) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editContent, setEditContent] = useState("");

  const handleEdit = (entry: MemoryEntry) => {
    setEditingId(entry.id);
    setEditContent(entry.content);
  };

  const handleSave = (entry: MemoryEntry) => {
    if (onSaveEdit) onSaveEdit(entry, editContent);
    setEditingId(null);
  };

  return (
    <div className="mb-6">
      <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">{title}</h2>
      <div className="space-y-2">
        {entries.length === 0 ? (
          <p className="text-xs text-text-muted italic">{emptyMessage || "No entries yet."}</p>
        ) : (
          entries.map((entry) =>
            editingId === entry.id ? (
              <div key={entry.id} className="bg-surface rounded-lg border border-border p-3">
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="w-full text-sm border border-border rounded-lg p-2 mb-2 focus:outline-none focus:ring-2 focus:ring-accent-ring text-text-primary bg-surface"
                  rows={3}
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => handleSave(entry)}
                    className="text-xs px-3 py-1 bg-accent text-white rounded-md hover:bg-accent-hover transition-colors"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="text-xs px-3 py-1 border border-border rounded-md text-text-secondary hover:bg-surface-tertiary transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <MemoryEntryCard
                key={entry.id}
                entry={entry}
                onPin={onPin}
                onEdit={handleEdit}
                onDelete={onDelete}
              />
            ),
          )
        )}
      </div>
    </div>
  );
}
