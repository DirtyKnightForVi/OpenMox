"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { CaretLeft, Plus, Trash, Star } from "@phosphor-icons/react";
import { useAppStore } from "@/stores/app";
import { listAgents, listTemplates, createAgent, deleteAgent } from "@/lib/api";

export default function AgentManagePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const projectName = params.id as string;
  const windowId = searchParams.get("window") || "";

  const { agents, setAgents, setTemplates, backToProjects } = useAppStore();
  const [templates, localTemplates] = useState<{ id: string; name: string; description: string }[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newAgentId, setNewAgentId] = useState("");
  const [newName, setNewName] = useState("");
  const [newTemplate, setNewTemplate] = useState("");

  useEffect(() => {
    listAgents(projectName).then(setAgents).catch(() => {});
    listTemplates().then((t) => { localTemplates(t); setTemplates(t); }).catch(() => {});
  }, [projectName, setAgents, setTemplates]);

  const handleCreate = async () => {
    if (!newAgentId || !newTemplate) return;
    await createAgent(projectName, newAgentId, newTemplate, newName || undefined);
    const updated = await listAgents(projectName);
    setAgents(updated);
    setShowAdd(false);
    setNewAgentId("");
    setNewName("");
  };

  const handleDelete = async (agentId: string) => {
    await deleteAgent(projectName, agentId);
    setAgents(agents.filter((a) => a.id !== agentId));
  };

  return (
    <div className="min-h-dvh bg-muted flex flex-col">
      <header className="flex items-center justify-between px-6 py-3 border-b border-border bg-white">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push(`/project/${projectName}?window=${windowId}`)} className="p-1.5 hover:bg-muted rounded-lg transition-colors text-text-secondary">
            <CaretLeft size={18} />
          </button>
          <span className="font-medium text-sm">{projectName}</span>
          <span className="text-xs text-text-muted">/ Team</span>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 px-3 py-1.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors"
        >
          <Plus size={16} />
          Add Member
        </button>
      </header>

      <main className="flex-1 max-w-3xl mx-auto w-full px-6 py-6 space-y-3">
        {agents.map((a) => (
          <div key={a.id} className="bg-white rounded-xl border border-border p-4 flex items-center gap-4">
            <div className={`size-10 rounded-full flex items-center justify-center text-sm font-bold ${a.is_momo ? "bg-blue-100 text-blue-700" : "bg-muted text-text-secondary"}`}>
              {a.id[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm">{a.name || a.id}</span>
                <span className="text-xs text-text-muted font-mono">({a.id})</span>
                {a.is_momo && <Star size={12} weight="fill" className="text-amber-500" />}
              </div>
              <div className="text-xs text-text-secondary mt-0.5 truncate">{a.description || "No description"}</div>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => handleDelete(a.id)}
                className="p-1.5 text-text-muted hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
              >
                <Trash size={16} />
              </button>
            </div>
          </div>
        ))}

        {/* Add dialog */}
        {showAdd && (
          <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50" onClick={() => setShowAdd(false)}>
            <div className="bg-white rounded-xl p-6 w-full max-w-lg shadow-lg border border-border" onClick={(e) => e.stopPropagation()}>
              <h3 className="font-semibold mb-4">Add New Member</h3>

              <div className="mb-4">
                <label className="text-xs font-medium text-text-secondary mb-1.5 block">Template</label>
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {templates.map((t) => (
                    <button key={t.id}
                      onClick={() => setNewTemplate(t.id)}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm border transition-colors ${
                        newTemplate === t.id
                          ? "border-accent bg-accent-soft text-accent"
                          : "border-border hover:border-accent/30"
                      }`}
                    >
                      <div className="font-medium">{t.name}</div>
                      <div className="text-xs text-text-muted">{t.description}</div>
                    </button>
                  ))}
                </div>
              </div>

              <input placeholder="Agent ID (e.g. pd-2)" value={newAgentId} onChange={(e) => setNewAgentId(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-lg mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30" />
              <input placeholder="Display name (optional)" value={newName} onChange={(e) => setNewName(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-lg mb-4 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30" />

              <div className="flex justify-end gap-2">
                <button onClick={() => setShowAdd(false)} className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors">Cancel</button>
                <button onClick={handleCreate} disabled={!newAgentId || !newTemplate}
                  className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-40 transition-colors">Create</button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
