"use client";

import { Folder, Clock, Users, ArrowRight, Plus, FolderOpen, Rocket } from "@phosphor-icons/react";
import { useAppStore } from "@/stores/app";
import { listProjects, createProject, listTemplates } from "@/lib/api";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Dialog } from "@/components/ui/Dialog";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { PathPicker } from "@/components/PathPicker";

const QUICK_TEMPLATES = [
  { id: "fullstack-dev", label: "Full-Stack Dev", icon: "🚀", desc: "PM + Architect + Developer" },
  { id: "backend-dev", label: "Backend Dev", icon: "⚙️", desc: "Architect + Developer + Reviewer" },
  { id: "research", label: "Research", icon: "🔬", desc: "Researcher + Analyst + Writer" },
];

export default function ProjectListPage() {
  const router = useRouter();
  const { projects, setProjects, setCurrentProject, setCurrentProjectPath } = useAppStore();
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPath, setNewPath] = useState("");
  const [showPicker, setShowPicker] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── Load projects ──
  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listProjects();
      setProjects(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }, [setProjects]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  // ── Create project ──
  const handleCreate = async () => {
    if (!newName || !newPath) return;
    try {
      await createProject(newName, newPath);
      await loadProjects();
      setShowNew(false);
      setNewName("");
      setNewPath("");
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to create project");
    }
  };

  // ── Quick create from template ──
  const handleQuickCreate = async (templateId: string) => {
    const name = `demo-${templateId}-${Date.now().toString(36)}`;
    const path = `/tmp/${name}`;
    try {
      await createProject(name, path, templateId);
      await loadProjects();
    } catch (e) {
      console.warn("Quick create failed:", e);
    }
  };

  // ── Navigate to project ──
  const openProject = (p: { name: string }) => {
    const wid = `web:s_${Date.now()}`;
    const project = projects.find((pr) => pr.name === p.name);
    if (project) {
      setCurrentProject(project, wid);
      if (project.full_path) setCurrentProjectPath(project.full_path);
    }
    router.push(`/project/${p.name}?window=${wid}`);
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
        {/* ── Loading state ── */}
        {loading && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 mb-4">
              <Folder size={14} className="text-text-muted" />
              <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Projects</span>
            </div>
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="w-full p-4 rounded-xl border border-border bg-surface animate-pulse"
              >
                <div className="flex items-center gap-3">
                  <div className="size-10 rounded-lg bg-surface-tertiary" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 w-32 bg-surface-tertiary rounded" />
                    <div className="h-3 w-48 bg-surface-tertiary rounded" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Error state ── */}
        {error && !loading && (
          <div className="text-center py-16">
            <div className="size-14 rounded-2xl bg-red-50 dark:bg-red-900/20 flex items-center justify-center mx-auto mb-4">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-red-500">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4M12 16h.01" />
              </svg>
            </div>
            <p className="text-sm font-medium text-text-primary mb-1">Failed to load projects</p>
            <p className="text-xs text-text-muted mb-4">{error}</p>
            <Button variant="secondary" size="sm" onClick={loadProjects}>
              Retry
            </Button>
          </div>
        )}

        {/* ── Empty state (first-run) ── */}
        {!loading && !error && projects.length === 0 && (
          <div className="text-center py-12">
            <div className="size-16 rounded-2xl bg-accent-soft flex items-center justify-center mx-auto mb-4">
              <Rocket size={32} className="text-accent" />
            </div>
            <h2 className="text-lg font-semibold text-text-primary mb-1">
              Welcome to OpenMox
            </h2>
            <p className="text-sm text-text-muted mb-6 max-w-sm mx-auto">
              Create a project and start collaborating with AI teammates.
            </p>

            {/* Quick-create template buttons */}
            <div className="flex flex-col sm:flex-row gap-3 justify-center mb-8">
              {QUICK_TEMPLATES.map((t) => (
                <button
                  key={t.id}
                  onClick={() => handleQuickCreate(t.id)}
                  className="flex items-center gap-3 px-4 py-3 rounded-xl border border-border bg-surface hover:border-accent/30 hover:shadow-xs transition-all text-left"
                >
                  <span className="text-lg">{t.icon}</span>
                  <div>
                    <div className="text-sm font-medium text-text-primary">{t.label}</div>
                    <div className="text-[11px] text-text-muted">{t.desc}</div>
                  </div>
                </button>
              ))}
            </div>

            <div className="flex items-center gap-3 text-xs text-text-muted mb-6">
              <span className="h-px flex-1 bg-border" />
              <span>or</span>
              <span className="h-px flex-1 bg-border" />
            </div>

            <Button onClick={() => setShowNew(true)} variant="secondary">
              <Plus size={16} />
              Create Custom Project
            </Button>
          </div>
        )}

        {/* ── Normal project list ── */}
        {!loading && !error && projects.length > 0 && (
          <>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider flex items-center gap-2">
                <Folder size={14} />
                Projects
                <span className="text-text-muted font-normal normal-case">
                  ({projects.length})
                </span>
              </h2>
              <div className="flex items-center gap-2">
                {QUICK_TEMPLATES.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => handleQuickCreate(t.id)}
                    className="text-[10px] px-2 py-1 rounded-md border border-border hover:bg-surface-tertiary text-text-muted hover:text-text-secondary transition-colors flex items-center gap-1"
                    title={`Quick create: ${t.label}`}
                  >
                    <span>{t.icon}</span>
                    <span className="hidden sm:inline">{t.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              {projects.map((p) => (
                <button
                  key={p.id}
                  onClick={() => openProject(p)}
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
                    <span>
                      {p.created_at
                        ? new Date(p.created_at).toLocaleDateString("zh-CN", {
                            month: "short",
                            day: "numeric",
                          })
                        : "Just now"}
                    </span>
                    <span className="mx-1 text-text-muted">·</span>
                    <Users size={12} />
                    <span>Multi-agent workspace</span>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </main>

      {/* ── Create dialog ── */}
      <Dialog open={showNew} onClose={() => setShowNew(false)} title="Create New Project">
        <Input
          label="Project Name"
          placeholder="my-awesome-project"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
        />
        <div className="mt-3">
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Input
                label="Full Path"
                placeholder="/tmp/my-project"
                value={newPath}
                onChange={(e) => setNewPath(e.target.value)}
              />
            </div>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setShowPicker(true)}
              className="mb-0"
            >
              <FolderOpen size={14} />
              Browse
            </Button>
          </div>
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

      <PathPicker
        open={showPicker}
        onClose={() => setShowPicker(false)}
        onSelect={(path) => { setNewPath(path); setShowPicker(false); }}
        initialPath={newPath || "/tmp"}
      />
    </div>
  );
}
