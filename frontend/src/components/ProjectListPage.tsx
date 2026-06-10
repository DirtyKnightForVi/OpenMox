"use client";

import { Folder, Clock, Users, ArrowRight, Plus } from "@phosphor-icons/react";
import { useAppStore } from "@/stores/app";
import { listProjects, createProject } from "@/lib/api";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Dialog } from "@/components/ui/Dialog";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

export default function ProjectListPage() {
  const router = useRouter();
  const { projects, setProjects, setCurrentProject } = useAppStore();
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPath, setNewPath] = useState("");

  useEffect(() => {
    listProjects().then(setProjects).catch(console.warn);
  }, [setProjects]);

  const handleCreate = async () => {
    if (!newName || !newPath) return;
    try {
      const result = await createProject(newName, newPath);
      if (!result.ok) {
        console.warn("Project creation returned unexpected failure", result);
        // result.ok=false with HTTP 200 only if backend changes; keep for safety
      }
      const updated = await listProjects();
      setProjects(updated);
      setShowNew(false);
      setNewName("");
      setNewPath("");
    } catch (e) {
      console.error("Failed to create project:", e);
      alert(e instanceof Error ? e.message : "Failed to create project");
    }
  };

  return (
    <div className="min-h-[100dvh] flex flex-col">
      <header className="flex items-center justify-between px-6 py-3 border-b border-border bg-surface">
        <div className="flex items-center gap-3">
          <div className="size-8 rounded-lg bg-accent flex items-center justify-center text-white font-bold text-sm">
            O
          </div>
          <h1 className="text-base font-semibold tracking-tight text-text-primary">OpenMox</h1>
        </div>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button onClick={() => setShowNew(true)} size="sm">
            <Plus size={16} weight="bold" />
            New Project
          </Button>
        </div>
      </header>

      <main className="flex-1 px-6 py-8 max-w-4xl mx-auto w-full">
        <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-4 flex items-center gap-2">
          <Folder size={14} />
          Projects
        </h2>

        <div className="space-y-2">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => {
                const wid = `web:s_${Date.now()}`;
                setCurrentProject(p, wid);
                router.push(`/project/${p.name}?window=${wid}`);
              }}
              className="w-full text-left p-4 rounded-xl border border-border bg-surface hover:border-accent/30 hover:shadow-xs transition-all group"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="size-10 rounded-lg bg-surface-tertiary flex items-center justify-center text-text-secondary">
                    <Folder size={20} weight="duotone" />
                  </div>
                  <div>
                    <div className="font-medium text-text-primary">{p.display_name || p.name}</div>
                    <div className="text-xs text-text-muted mt-0.5">{p.full_path}</div>
                  </div>
                </div>
                <ArrowRight size={16} className="text-text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <div className="flex items-center gap-2 mt-3 text-xs text-text-secondary">
                <Clock size={12} />
                <span>Agent project</span>
                <span className="mx-1 text-text-muted">·</span>
                <Users size={12} />
                <span>Multi-agent workspace</span>
              </div>
            </button>
          ))}
        </div>
      </main>

      <Dialog open={showNew} onClose={() => setShowNew(false)} title="Create New Project">
        <Input
          label="Project Name"
          placeholder="my-awesome-project"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
        />
        <div className="mt-3">
          <Input
            label="Full Path"
            placeholder="/home/user/projects/my-app"
            value={newPath}
            onChange={(e) => setNewPath(e.target.value)}
          />
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <Button variant="secondary" onClick={() => setShowNew(false)}>
            Cancel
          </Button>
          <Button onClick={handleCreate} disabled={!newName || !newPath}>
            Create
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
