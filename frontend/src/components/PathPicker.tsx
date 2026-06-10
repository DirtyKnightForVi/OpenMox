"use client";

import { Folder, FolderOpen, ArrowUp, X, Check } from "@phosphor-icons/react";
import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Dialog } from "@/components/ui/Dialog";

interface DirEntry {
  name: string;
  path: string;
  type: "dir";
}

interface FsResponse {
  current: string;
  parent: string | null;
  entries: DirEntry[];
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
  initialPath?: string;
}

async function fetchDir(path: string): Promise<FsResponse> {
  const res = await fetch(`http://localhost:8000/api/fs/ls?path=${encodeURIComponent(path)}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Cannot read ${path}`);
  }
  return res.json();
}

/** A directory browser modal — user navigates and clicks Select to pick. */
export function PathPicker({ open, onClose, onSelect, initialPath = "/" }: Props) {
  const [current, setCurrent] = useState(initialPath);
  const [entries, setEntries] = useState<DirEntry[]>([]);
  const [parent, setParent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // editable path bar
  const [pathInput, setPathInput] = useState(initialPath);

  const load = useCallback(async (p: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDir(p);
      setCurrent(data.current);
      setParent(data.parent);
      setEntries(data.entries);
      setPathInput(data.current);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) load(initialPath);
  }, [open, initialPath, load]);

  const handlePathInputKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") load(pathInput);
  };

  return (
    <Dialog open={open} onClose={onClose} title="Choose Project Directory">
      {/* ── Path bar ────────────────────────────── */}
      <div className="flex items-center gap-2">
        <Input
          className="flex-1 font-mono text-xs"
          value={pathInput}
          onChange={(e) => setPathInput(e.target.value)}
          onKeyDown={handlePathInputKey}
        />
        <Button size="sm" variant="secondary" onClick={() => load(pathInput)} disabled={loading}>
          Go
        </Button>
      </div>

      {/* ── Parent link ─────────────────────────── */}
      {parent && (
        <button
          className="mt-2 w-full text-left px-2 py-1 rounded hover:bg-surface-tertiary text-text-secondary text-sm flex items-center gap-2"
          onClick={() => load(parent)}
        >
          <ArrowUp size={14} />
          ..
        </button>
      )}

      {/* ── Directory listing ───────────────────── */}
      <div className="mt-1 border border-border rounded-lg max-h-64 overflow-y-auto">
        {loading && <div className="px-3 py-4 text-sm text-text-muted">Loading…</div>}
        {error && <div className="px-3 py-4 text-sm text-red-500">{error}</div>}
        {!loading &&
          !error &&
          entries.length === 0 && (
            <div className="px-3 py-4 text-sm text-text-muted">
              No subdirectories.
            </div>
          )}
        {entries.map((e) => (
          <button
            key={e.path}
            className="w-full text-left px-3 py-2 hover:bg-accent/10 flex items-center gap-2 text-sm transition-colors"
            onClick={() => load(e.path)}
          >
            <Folder size={16} className="text-text-secondary flex-shrink-0" />
            <span className="truncate">{e.name}</span>
          </button>
        ))}
      </div>

      {/* ── Actions ─────────────────────────────── */}
      <div className="flex justify-between items-center mt-4">
        <div className="text-xs text-text-muted font-mono truncate max-w-[300px]" title={current}>
          {current}
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            <X size={14} />
            Cancel
          </Button>
          <Button size="sm" onClick={() => onSelect(current)}>
            <Check size={14} />
            Select
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
