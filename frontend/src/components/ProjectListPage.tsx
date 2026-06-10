"use client";

import { Folder, Plus, Clock, Users, ArrowRight } from "@phosphor-icons/react";
import { useAppStore } from "@/stores/app";
import { listProjects, createProject } from "@/lib/api";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const agentColor = (id: string) => {
  const colors = ["bg-blue-100 text-blue-700", "bg-amber-100 text-amber-700", "bg-indigo-100 text-indigo-700", "bg-rose-100 text-rose-700", "bg-emerald-100 text-emerald-700"];
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = id.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
};

export default function ProjectListPage() {
  const router = useRouter();
  const { projects, agents, setProjects, setCurrentProject, setAgents } = useAppStore();
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPath, setNewPath] = useState("");

  useEffect(() => {
    listProjects().then(setProjects).catch(console.warn);
  }, [setProjects]);

  useEffect(() => {
    import("@/lib/api").then((api) => api.listAgents().then(setAgents).catch(() => {}));
  }, [setAgents]);

  const handleCreate = async () => {
    if (!newName || !newPath) return;
    await createProject(newName, newPath);
    const updated = await listProjects();
    setProjects(updated);
    setShowNew(false);
    setNewName("");
    setNewPath("");
  };

  return (
    <div className="min-h-dvh flex flex-col">
      <header className="flex items-center justify-between px-8 py-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="size-8 rounded-lg bg-accent flex items-center justify-center text-white font-bold text-sm">O</div>
          <h1 className="text-lg font-semibold tracking-tight">OpenMox</h1>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-2 px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors"
        >
          <Plus size={16} weight="bold" />
          New Project
        </button>
      </header>

      <main className="flex-1 px-8 py-8 max-w-4xl mx-auto w-full">
        <h2 className="text-sm font-medium text-text-secondary mb-4 flex items-center gap-2">
          <Folder size={16} />
          Projects
        </h2>

        <div className="space-y-3">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => {
                const wid = `web:s_${Date.now()}`;
                setCurrentProject(p, wid);
                router.push(`/project/${p.name}?window=${wid}`);
              }}
              className="w-full text-left p-4 rounded-xl border border-border bg-white hover:border-accent/30 hover:shadow-xs transition-all group"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="size-10 rounded-lg bg-muted flex items-center justify-center text-text-secondary">
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
                <span>Last opened recently</span>
                <span className="mx-1">·</span>
                <Users size={12} />
                <span>Agent project</span>
              </div>
            </button>
          ))}
        </div>

        {/* New Project Dialog */}
        {showNew && (
          <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50" onClick={() => setShowNew(false)}>
            <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-lg border border-border" onClick={(e) => e.stopPropagation()}>
              <h3 className="font-semibold mb-4">Create New Project</h3>
              <input
                placeholder="Project name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-lg mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
              />
              <input
                placeholder="Full path (e.g. /home/user/projects/my-app)"
                value={newPath}
                onChange={(e) => setNewPath(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-lg mb-4 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
              />
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowNew(false)} className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors">
                  Cancel
                </button>
                <button
                  onClick={handleCreate}
                  disabled={!newName || !newPath}
                  className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-40 transition-colors"
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
