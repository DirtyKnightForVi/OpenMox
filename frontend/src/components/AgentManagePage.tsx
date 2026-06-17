"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { Plus } from "@phosphor-icons/react";
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
  const projectName = params.id as string;

  const { agents, setAgents } = useAppStore();
  const [templates, setTemplates] = useState<{ id: string; name: string; description: string; skills_count: number }[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newAgentId, setNewAgentId] = useState("");
  const [newName, setNewName] = useState("");
  const [newTemplate, setNewTemplate] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      listAgents(projectName).then(setAgents),
      listTemplates().then(setTemplates),
    ])
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [projectName, setAgents]);

  const handleCreate = async () => {
    if (!newAgentId || !newTemplate) return;
    try {
      await createAgent(projectName, newAgentId, newTemplate, newName || undefined);
      const updated = await listAgents(projectName);
      setAgents(updated);
      setShowAdd(false);
      setNewAgentId("");
      setNewName("");
      setNewTemplate("");
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to create agent");
    }
  };

  const handleDelete = async (agentId: string) => {
    try {
      await deleteAgent(projectName, agentId);
      setAgents(agents.filter((a) => a.id !== agentId));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to delete agent");
    }
  };

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-border bg-surface shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-semibold text-text-primary">Team</h1>
          <span className="text-xs text-text-muted">
            {agents.length} {agents.length === 1 ? "member" : "members"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button onClick={() => setShowAdd(true)} size="sm">
            <Plus size={16} />
            Add Member
          </Button>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-3xl mx-auto space-y-2">
          {/* Loading state */}
          {loading && (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="bg-surface rounded-xl border border-border p-4 animate-pulse">
                  <div className="flex items-center gap-4">
                    <div className="size-10 rounded-full bg-surface-tertiary" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 w-24 bg-surface-tertiary rounded" />
                      <div className="h-3 w-48 bg-surface-tertiary rounded" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Error state */}
          {error && !loading && (
            <div className="text-center py-12">
              <p className="text-sm text-red-500 mb-2">Failed to load team members</p>
              <p className="text-xs text-text-muted mb-4">{error}</p>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setLoading(true);
                  setError(null);
                  Promise.all([
                    listAgents(projectName).then(setAgents),
                    listTemplates().then(setTemplates),
                  ])
                    .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
                    .finally(() => setLoading(false));
                }}
              >
                Retry
              </Button>
            </div>
          )}

          {/* Empty state */}
          {!loading && !error && agents.length === 0 && (
            <div className="text-center py-16">
              <div className="size-16 rounded-2xl bg-surface-tertiary flex items-center justify-center mx-auto mb-4">
                <UsersThreeIcon />
              </div>
              <p className="text-sm font-medium text-text-primary">
                Your team is empty
              </p>
              <p className="text-xs text-text-muted mt-1 mb-4 max-w-xs mx-auto">
                Only momo isn't enough. Add team members to make the team stronger.
              </p>
              <Button onClick={() => setShowAdd(true)} variant="secondary">
                <Plus size={16} />
                Add your first member
              </Button>
            </div>
          )}

          {/* Normal list */}
          {!loading && !error && agents.map((a) => (
            <AgentCard key={a.id} agent={a} onDelete={handleDelete} />
          ))}
        </div>
      </main>

      {/* Add dialog */}
      <Dialog open={showAdd} onClose={() => setShowAdd(false)} title="Add New Member">
        <div className="mb-4">
          <label className="text-xs font-medium text-text-secondary mb-1.5 block">Template</label>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {templates.length === 0 && (
              <p className="text-xs text-text-muted px-2 py-3">No templates available</p>
            )}
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

/** Inline icon to avoid heavy imports */
function UsersThreeIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 256 256" fill="none" stroke="currentColor" strokeWidth="12" className="text-text-muted">
      <circle cx="88" cy="108" r="40" />
      <circle cx="192" cy="108" r="32" />
      <path d="M32 200c0-30.9 25.1-56 56-56s56 25.1 56 56" />
      <path d="M160 200c0-24.9 20.1-45 45-45s45 20.1 45 45" />
    </svg>
  );
}
