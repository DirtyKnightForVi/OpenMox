"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { CaretLeft, ArrowsClockwise, MoonStars, ClockCounterClockwise, PushPin, PencilSimple, Trash } from "@phosphor-icons/react";
import { useAppStore } from "@/stores/app";
import { listMemory, updateMemory, triggerReflect, listAgents } from "@/lib/api";
import type { MemoryEntry } from "@/lib/types";

const typeLabels: Record<string, { label: string; color: string }> = {
  fact: { label: "Fact", color: "bg-emerald-100 text-emerald-700" },
  decision: { label: "Decision", color: "bg-blue-100 text-blue-700" },
  reflection: { label: "Reflection", color: "bg-purple-100 text-purple-700" },
  shendu: { label: "慎独", color: "bg-indigo-100 text-indigo-700" },
  preference: { label: "Preference", color: "bg-amber-100 text-amber-700" },
  context: { label: "Context", color: "bg-gray-100 text-gray-600" },
};

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
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editContent, setEditContent] = useState("");

  useEffect(() => {
    listAgents(projectName).then((a) => { setAgents(a); if (!selectedAgent && a.length > 0) setSelectedAgent(a[0].id); }).catch(() => {});
  }, [projectName, setAgents]);

  useEffect(() => {
    if (!selectedAgent) return;
    listMemory(selectedAgent, "private").then((r) => setPrivateMems(r.entries)).catch(() => {});
    listMemory(selectedAgent, "shared").then((r) => setSharedMems(r.entries)).catch(() => {});
  }, [selectedAgent]);

  const handlePin = async (entry: MemoryEntry) => {
    await updateMemory(selectedAgent, entry.id, { pinned: entry.pinned ? 0 : 1 });
    const updated = await listMemory(selectedAgent, entry.scope);
    if (entry.scope === "private") setPrivateMems(updated.entries);
    else setSharedMems(updated.entries);
  };

  const handleDelete = async (entry: MemoryEntry) => {
    await updateMemory(selectedAgent, entry.id, { deprecated: 1 });
    if (entry.scope === "private") setPrivateMems((prev) => prev.filter((e) => e.id !== entry.id));
    else setSharedMems((prev) => prev.filter((e) => e.id !== entry.id));
  };

  const handleSaveEdit = async (entry: MemoryEntry) => {
    await updateMemory(selectedAgent, entry.id, { content: editContent });
    setEditingId(null);
    const updated = await listMemory(selectedAgent, entry.scope);
    if (entry.scope === "private") setPrivateMems(updated.entries);
    else setSharedMems(updated.entries);
  };

  const renderEntries = (entries: MemoryEntry[], title: string) => (
    <div className="mb-6">
      <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">{title}</h2>
      <div className="space-y-2">
        {entries.length === 0 && <p className="text-xs text-text-muted italic">No entries yet.</p>}
        {entries.map((entry) => (
          <div key={entry.id} className="bg-white rounded-lg border border-border p-3">
            {editingId === entry.id ? (
              <div>
                <textarea value={editContent} onChange={(e) => setEditContent(e.target.value)}
                  className="w-full text-sm border border-border rounded-lg p-2 mb-2 focus:outline-none focus:ring-2 focus:ring-accent/30" rows={3} />
                <div className="flex gap-2">
                  <button onClick={() => handleSaveEdit(entry)} className="text-xs px-3 py-1 bg-accent text-white rounded-md">Save</button>
                  <button onClick={() => setEditingId(null)} className="text-xs px-3 py-1 border border-border rounded-md text-text-secondary">Cancel</button>
                </div>
              </div>
            ) : (
              <div>
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm leading-relaxed flex-1">{entry.content}</p>
                  <div className="flex items-center gap-1 shrink-0">
                    <button onClick={() => handlePin(entry)}
                      className={`p-1 rounded transition-colors ${entry.pinned ? "text-amber-500" : "text-text-muted hover:text-text-secondary"}`}>
                      <PushPin size={14} weight={entry.pinned ? "fill" : "regular"} />
                    </button>
                    <button onClick={() => { setEditingId(entry.id); setEditContent(entry.content); }}
                      className="p-1 text-text-muted hover:text-text-secondary rounded transition-colors"><PencilSimple size={14} /></button>
                    <button onClick={() => handleDelete(entry)}
                      className="p-1 text-text-muted hover:text-red-500 rounded transition-colors"><Trash size={14} /></button>
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${typeLabels[entry.type]?.color || "bg-gray-100 text-gray-600"}`}>
                    {typeLabels[entry.type]?.label || entry.type}
                  </span>
                  <span className="text-[10px] text-text-muted">{new Date(entry.created_at).toLocaleString()}</span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="min-h-dvh bg-muted flex flex-col">
      <header className="flex items-center justify-between px-6 py-3 border-b border-border bg-white">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push(`/project/${projectName}?window=${windowId}`)} className="p-1.5 hover:bg-muted rounded-lg transition-colors text-text-secondary">
            <CaretLeft size={18} />
          </button>
          <span className="font-medium text-sm">{projectName}</span>
          <span className="text-xs text-text-muted">/ Memory</span>
        </div>
        <div className="flex items-center gap-2">
          <select value={selectedAgent} onChange={(e) => setSelectedAgent(e.target.value)}
            className="text-sm border border-border rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-accent/30">
            {agents.map((a) => <option key={a.id} value={a.id}>{a.name || a.id}</option>)}
          </select>
          <button onClick={async () => { if (selectedAgent) { await triggerReflect(selectedAgent, "quick", windowId); const r = await listMemory(selectedAgent, "private"); setPrivateMems(r.entries); }}}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-border rounded-lg text-xs hover:bg-muted transition-colors">
            <ArrowsClockwise size={14} /> Quick Reflect
          </button>
          <button onClick={async () => { if (selectedAgent) { await triggerReflect(selectedAgent, "shendu"); const r = await listMemory(selectedAgent, "private"); setPrivateMems(r.entries); }}}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-border rounded-lg text-xs hover:bg-muted transition-colors">
            <MoonStars size={14} /> Shendu
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-3xl mx-auto w-full px-6 py-6">
        {renderEntries(privateMems, "Your Memory (private)")}
        <div className="border-t border-border pt-6 mt-6">
          {renderEntries(sharedMems, "Project Consensus (shared)")}
        </div>
      </main>
    </div>
  );
}
