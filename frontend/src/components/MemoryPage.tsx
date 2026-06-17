"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useAppStore } from "@/stores/app";
import { listMemory, updateMemory, triggerReflect, rollbackSnapshot, listAgents } from "@/lib/api";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { Button } from "@/components/ui/Button";
import { MemoryList } from "@/components/memory/MemoryList";
import { ReflectButtons } from "@/components/memory/ReflectButtons";
import { AgentSelector } from "@/components/agents/AgentSelector";
import type { MemoryEntry } from "@/lib/types";

export default function MemoryPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectName = params.id as string;
  const urlAgent = searchParams.get("agent") || "";

  const { agents, setAgents } = useAppStore();
  const [selectedAgent, setSelectedAgent] = useState(urlAgent);
  const [privateMems, setPrivateMems] = useState<MemoryEntry[]>([]);
  const [sharedMems, setSharedMems] = useState<MemoryEntry[]>([]);
  const [isReflecting, setIsReflecting] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAgents(projectName)
      .then((a) => {
        setAgents(a);
        if (!selectedAgent && a.length > 0) setSelectedAgent(a[0].id);
      })
      .catch(() => {});
  }, [projectName, setAgents]);

  useEffect(() => {
    if (!selectedAgent) return;
    setLoading(true);
    setError(null);
    Promise.all([
      listMemory(selectedAgent, "private"),
      listMemory(selectedAgent, "shared"),
    ])
      .then(([priv, shared]) => {
        setPrivateMems(priv.entries);
        setSharedMems(shared.entries);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load memory"))
      .finally(() => setLoading(false));
  }, [selectedAgent]);

  const refreshMemories = async (agentId: string) => {
    try {
      const [priv, shared] = await Promise.all([
        listMemory(agentId, "private"),
        listMemory(agentId, "shared"),
      ]);
      setPrivateMems(priv.entries);
      setSharedMems(shared.entries);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to refresh");
    }
  };

  const handlePin = async (entry: MemoryEntry) => {
    if (!selectedAgent) return;
    await updateMemory(selectedAgent, entry.id, { pinned: entry.pinned ? 0 : 1 });
    refreshMemories(selectedAgent);
  };

  const handleSaveEdit = async (entry: MemoryEntry, content: string) => {
    if (!selectedAgent) return;
    await updateMemory(selectedAgent, entry.id, { content });
    refreshMemories(selectedAgent);
  };

  const handleDelete = async (entry: MemoryEntry) => {
    if (!selectedAgent) return;
    await updateMemory(selectedAgent, entry.id, { deprecated: 1 });
    if (entry.scope === "private") {
      setPrivateMems((prev) => prev.filter((e) => e.id !== entry.id));
    } else {
      setSharedMems((prev) => prev.filter((e) => e.id !== entry.id));
    }
  };

  const handleQuickReflect = async () => {
    if (!selectedAgent) return;
    setIsReflecting(true);
    await triggerReflect(selectedAgent, "quick", searchParams.get("window") || undefined);
    await refreshMemories(selectedAgent);
    setIsReflecting(false);
  };

  const handleShenduReflect = async () => {
    if (!selectedAgent) return;
    setIsReflecting(true);
    await triggerReflect(selectedAgent, "shendu");
    await refreshMemories(selectedAgent);
    setIsReflecting(false);
  };

  const handleSync = async () => {
    if (!selectedAgent) return;
    setIsSyncing(true);
    try {
      const res = await fetch(`http://localhost:8000/api/memory/${selectedAgent}/sync`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Sync failed");
    } catch (e) {
      console.warn("Sync error:", e);
    }
    setIsSyncing(false);
  };

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-border bg-surface shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-semibold text-text-primary">Memory</h1>
          {agents.length > 0 && (
            <AgentSelector
              agents={agents}
              value={selectedAgent}
              onChange={setSelectedAgent}
            />
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={handleSync} disabled={isSyncing || !selectedAgent}>
            {isSyncing ? "Syncing..." : "Sync to File"}
          </Button>
          <ReflectButtons
            onQuickReflect={handleQuickReflect}
            onShenduReflect={handleShenduReflect}
            isLoading={isReflecting}
          />
          <ThemeToggle />
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-3xl mx-auto">
          {/* Loading state */}
          {loading && selectedAgent && (
            <div className="space-y-3">
              <div className="h-4 w-32 bg-surface-tertiary rounded animate-pulse mb-4" />
              {[1, 2, 3].map((i) => (
                <div key={i} className="bg-surface rounded-lg border border-border p-3 animate-pulse">
                  <div className="h-4 w-full bg-surface-tertiary rounded mb-2" />
                  <div className="h-3 w-24 bg-surface-tertiary rounded" />
                </div>
              ))}
            </div>
          )}

          {/* Error state */}
          {error && !loading && (
            <div className="text-center py-12">
              <p className="text-sm text-red-500 mb-2">Failed to load memories</p>
              <p className="text-xs text-text-muted mb-4">{error}</p>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => selectedAgent && refreshMemories(selectedAgent)}
              >
                Retry
              </Button>
            </div>
          )}

          {/* No agent selected */}
          {!selectedAgent && !loading && (
            <div className="text-center py-16">
              <p className="text-sm text-text-muted">Select an agent to view their memories</p>
            </div>
          )}

          {/* Memory lists */}
          {selectedAgent && !loading && !error && (
            <>
              <MemoryList
                entries={privateMems}
                title="Private Memory"
                emptyMessage="No private memories yet. Start working and agents will extract them automatically."
                onPin={handlePin}
                onSaveEdit={handleSaveEdit}
                onDelete={handleDelete}
              />
              <div className="border-t border-border pt-6 mt-6">
                <MemoryList
                  entries={sharedMems}
                  title="Project Consensus (shared)"
                  emptyMessage="No shared memories yet. Cross-agent reflections will appear here."
                  onPin={handlePin}
                  onSaveEdit={handleSaveEdit}
                  onDelete={handleDelete}
                />
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
