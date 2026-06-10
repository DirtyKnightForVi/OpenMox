"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { CaretLeft } from "@phosphor-icons/react";
import { useAppStore } from "@/stores/app";
import { listMemory, updateMemory, triggerReflect, listAgents } from "@/lib/api";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { MemoryList } from "@/components/memory/MemoryList";
import { ReflectButtons } from "@/components/memory/ReflectButtons";
import type { MemoryEntry } from "@/lib/types";

export default function MemoryPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const projectName = params.id as string;
  const windowId = searchParams.get("window") || "";

  const { agents, setAgents } = useAppStore();
  const [selectedAgent, setSelectedAgent] = useState("");
  const [privateMems, setPrivateMems] = useState<MemoryEntry[]>([]);
  const [sharedMems, setSharedMems] = useState<MemoryEntry[]>([]);
  const [isReflecting, setIsReflecting] = useState(false);

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
    listMemory(selectedAgent, "private")
      .then((r) => setPrivateMems(r.entries))
      .catch(() => {});
    listMemory(selectedAgent, "shared")
      .then((r) => setSharedMems(r.entries))
      .catch(() => {});
  }, [selectedAgent]);

  const refreshMemories = async (agentId: string) => {
    const [priv, shared] = await Promise.all([
      listMemory(agentId, "private"),
      listMemory(agentId, "shared"),
    ]);
    setPrivateMems(priv.entries);
    setSharedMems(shared.entries);
  };

  const handlePin = async (entry: MemoryEntry) => {
    await updateMemory(selectedAgent, entry.id, { pinned: entry.pinned ? 0 : 1 });
    refreshMemories(selectedAgent);
  };

  const handleSaveEdit = async (entry: MemoryEntry, content: string) => {
    await updateMemory(selectedAgent, entry.id, { content });
    refreshMemories(selectedAgent);
  };

  const handleDelete = async (entry: MemoryEntry) => {
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
    await triggerReflect(selectedAgent, "quick", windowId);
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

  return (
    <div className="min-h-[100dvh] bg-surface-secondary flex flex-col">
      <header className="flex items-center justify-between px-6 py-3 border-b border-border bg-surface">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push(`/project/${projectName}?window=${windowId}`)}
            className="p-1.5 hover:bg-surface-tertiary rounded-lg transition-colors text-text-secondary"
          >
            <CaretLeft size={18} />
          </button>
          <span className="font-medium text-sm text-text-primary">{projectName}</span>
          <span className="text-xs text-text-muted">/ Memory</span>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            className="text-sm border border-border rounded-lg px-3 py-1.5 bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-ring"
          >
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name || a.id}
              </option>
            ))}
          </select>
          <ReflectButtons
            onQuickReflect={handleQuickReflect}
            onShenduReflect={handleShenduReflect}
            isLoading={isReflecting}
          />
          <ThemeToggle />
        </div>
      </header>

      <main className="flex-1 max-w-3xl mx-auto w-full px-6 py-6">
        <MemoryList
          entries={privateMems}
          title="Your Memory (private)"
          onPin={handlePin}
          onSaveEdit={handleSaveEdit}
          onDelete={handleDelete}
        />
        <div className="border-t border-border pt-6 mt-6">
          <MemoryList
            entries={sharedMems}
            title="Project Consensus (shared)"
            onPin={handlePin}
            onSaveEdit={handleSaveEdit}
            onDelete={handleDelete}
          />
        </div>
      </main>
    </div>
  );
}
