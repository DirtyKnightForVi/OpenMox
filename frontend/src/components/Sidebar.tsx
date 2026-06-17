"use client";

import { useParams, usePathname, useRouter } from "next/navigation";
import { useAppStore } from "@/stores/app";
import {
  ChatCircleDots,
  UsersThree,
  Brain,
  SquaresFour,
  CaretLeft,
} from "@phosphor-icons/react";
import { clsx } from "clsx";

interface NavItem {
  href: string;
  icon: React.ElementType;
  label: string;
  match: (pathname: string, project: string) => boolean;
}

const NAV_ITEMS: NavItem[] = [
  {
    href: "",
    icon: ChatCircleDots,
    label: "Workbench",
    match: (p, project) => p === `/project/${project}`,
  },
  {
    href: "/agents",
    icon: UsersThree,
    label: "Team",
    match: (p, project) => p === `/project/${project}/agents`,
  },
  {
    href: "/memory",
    icon: Brain,
    label: "Memory",
    match: (p, project) => p === `/project/${project}/memory`,
  },
];

export function Sidebar() {
  const params = useParams();
  const pathname = usePathname();
  const router = useRouter();
  const projectName = (params.id as string) || "";
  const { agents, tasks, currentProject, currentWindowId, backToProjects } = useAppStore();

  const activeTasks = tasks.filter((t) => t.status === "in_progress").length;
  const hasBack = pathname !== "/";

  return (
    <aside className="w-56 shrink-0 bg-surface border-r border-border flex flex-col h-full">
      {/* Project name + back */}
      <div className="px-4 pt-4 pb-3">
        {hasBack && (
          <button
            onClick={() => {
              backToProjects();
              router.push("/");
            }}
            className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-secondary transition-colors mb-2"
          >
            <CaretLeft size={14} />
            <span>All Projects</span>
          </button>
        )}
        <div className="flex items-center gap-2.5">
          <div className="size-8 rounded-lg bg-accent flex items-center justify-center text-white font-bold text-sm shrink-0">
            {projectName ? projectName[0].toUpperCase() : "O"}
          </div>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-text-primary truncate">
              {currentProject?.display_name || projectName || "OpenMox"}
            </div>
            {agents.length > 0 && (
              <div className="text-[11px] text-text-muted mt-0.5">
                {agents.length} {agents.length === 1 ? "member" : "members"}
                {activeTasks > 0 && ` · ${activeTasks} active`}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Project nav */}
      <nav className="flex-1 px-2 py-2 space-y-0.5">
        <div className="text-[10px] font-semibold text-text-muted uppercase tracking-wider px-2 pb-1">
          {projectName || "Project"}
        </div>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = item.match(pathname, projectName);
          const navUrl = currentWindowId
            ? `/project/${projectName}${item.href}?window=${currentWindowId}`
            : `/project/${projectName}${item.href}`;
          return (
            <button
              key={item.href}
              onClick={() => router.push(navUrl)}
              className={clsx(
                "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors text-left",
                isActive
                  ? "bg-accent-soft text-accent font-medium"
                  : "text-text-secondary hover:bg-surface-tertiary hover:text-text-primary",
              )}
            >
              <Icon size={18} weight={isActive ? "fill" : "regular"} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Bottom section */}
      <div className="px-2 pb-3 pt-2 border-t border-border">
        <button
          onClick={() => router.push("/")}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-text-secondary hover:bg-surface-tertiary hover:text-text-primary transition-colors"
        >
          <SquaresFour size={18} />
          <span>Project List</span>
        </button>
      </div>
    </aside>
  );
}
