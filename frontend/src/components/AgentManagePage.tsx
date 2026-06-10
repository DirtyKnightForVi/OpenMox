"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { CaretLeft, Plus } from "@phosphor-icons/react";
import { useAppStore } from "@/stores/app";
import { listAgents, listTemplates, createAgent, deleteAgent } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Dialog } from "@/components/ui/Dialog";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { AgentCard } from "@/components/agents/AgentCard";
import { clsx } from "clsx";

export default function AgentManagePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const projectName = params.id as string;
  const windowId = searchParams.get("window") || "";

  const { agents, setAgents } = useAppStore();
  const [templates, setTemplates] = useState<{ id: string; name: string; description: string; skills_count: number }[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newAgentId, setNewAgentId] = useState("");
  const [newName, setNewName] = useState("");
  const [newTemplate, setNewTemplate] = useState("");

  useEffect(() => {
    listAgents(projectName).then(setAgents).catch(() => {});
    listTemplates().then(setTemplates).catch(() => {});
  }, [projectName, setAgents]);

  const handleCreate = async () => {
    if (!newAgentId || !newTemplate) return;
    await createAgent(projectName, newAgentId, newTemplate, newName || undefined);
    const updated = await listAgents(projectName);
    setAgents(updated);
    setShowAdd(false);
    setNewAgentId("");
    setNewName("");
    setNewTemplate("");
  };

  const handleDelete = async (agentId: string) => {
    await deleteAgent(projectName, agentId);
    setAgents(agents.filter((a) => a.id !== agentId));
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
          <span className="text-xs text-text-muted">/ Team</span>
        </div>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button onClick={() => setShowAdd(true)} size="sm">
            <Plus size={16} />
            Add Member
          </Button>
        </div>
      </header>

      <main className="flex-1 max-w-3xl mx-auto w-full px-6 py-6 space-y-2">
        {agents.length === 0 && (
          <div className="text-center py-12">
            <p className="text-sm text-text-muted">No team members yet.</p>
            <Button onClick={() => setShowAdd(true)} variant="secondary" className="mt-3">
              <Plus size={16} />
              Add your first member
            </Button>
          </div>
        )}
        {agents.map((a) => (
          <AgentCard key={a.id} agent={a} onDelete={handleDelete} />
        ))}
      </main>

      <Dialog open={showAdd} onClose={() => setShowAdd(false)} title="Add New Member">
        <div className="mb-4">
          <label className="text-xs font-medium text-text-secondary mb-1.5 block">Template</label>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {templates.map((t) => (
              <button
                key={t.id}
                onClick={() => setNewTemplate(t.id)}
                className={clsx(
                  "w-full text-left px-3 py-2 rounded-lg text-sm border transition-colors",
                  newTemplate === t.id
                    ? "border-accent bg-accent-soft text-accent"
                    : "border-border hover:border-accent/30",
                )}
              >
                <div className="font-medium">{t.name || t.id}</div>
                <div className="text-xs text-text-muted">{t.description}</div>
              </button>
            ))}
          </div>
        </div>

        <Input
          label="Agent ID"
          placeholder="e.g. pd-2"
          value={newAgentId}
          onChange={(e) => setNewAgentId(e.target.value)}
        />
        <div className="mt-3">
          <Input
            label="Display Name (optional)"
            placeholder="Product Designer"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
        </div>

        <div className="flex justify-end gap-2 mt-5">
          <Button variant="secondary" onClick={() => setShowAdd(false)}>
            Cancel
          </Button>
          <Button onClick={handleCreate} disabled={!newAgentId || !newTemplate}>
            Create
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
