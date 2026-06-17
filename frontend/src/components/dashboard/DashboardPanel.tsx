"use client";

import { useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { TaskSkeleton } from "@/components/ui/Skeleton";
import { PhaseColumn } from "./PhaseColumn";
import { updateDashboardTask } from "@/lib/api";
import { useAppStore } from "@/stores/app";
import type { Task } from "@/lib/types";

interface DashboardPanelProps {
  tasks: Task[];
  isLoading?: boolean;
}

const PHASE_CONFIG = [
  { key: "research", label: "Research", color: "bg-blue-500" },
  { key: "development", label: "Development", color: "bg-amber-500" },
  { key: "review", label: "Review", color: "bg-indigo-500" },
  { key: "delivery", label: "Delivery", color: "bg-emerald-500" },
] as const;

export function DashboardPanel({ tasks, isLoading }: DashboardPanelProps) {
  const searchParams = useSearchParams();
  const { setTasks } = useAppStore();
  const windowId = searchParams.get("window") || "";

  const handleTaskDrop = useCallback(
    async (taskId: string, fromPhase: string, toPhase: string) => {
      // Optimistic update
      setTasks(
        tasks.map((t) => (t.id === taskId ? { ...t, phase: toPhase as Task["phase"] } : t)),
      );
      try {
        await updateDashboardTask(taskId, { phase: toPhase });
      } catch {
        // Rollback on failure
        setTasks(
          tasks.map((t) => (t.id === taskId ? { ...t, phase: fromPhase as Task["phase"] } : t)),
        );
      }
    },
    [tasks, setTasks],
  );

  if (isLoading) {
    return (
      <div className="p-4">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">Tasks</h3>
        <TaskSkeleton />
      </div>
    );
  }

  const totalCount = tasks.length;
  const doneCount = tasks.filter((t) => t.status === "done").length;

  return (
    <div className="p-4 border-b border-border">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Tasks</h3>
        {totalCount > 0 && (
          <span className="text-[10px] text-text-muted">
            {doneCount}/{totalCount} done
          </span>
        )}
      </div>

      {totalCount === 0 ? (
        <div className="text-center py-6">
          <div className="size-10 rounded-full bg-surface-tertiary flex items-center justify-center mx-auto mb-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-text-muted">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M9 12l2 2 4-4" />
            </svg>
          </div>
          <p className="text-xs text-text-muted mb-1">No tasks yet</p>
          <p className="text-[10px] text-text-muted">
            @momo to create tasks
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {PHASE_CONFIG.map(({ key, label, color }) => (
            <PhaseColumn
              key={key}
              phase={key}
              tasks={tasks.filter((t) => t.phase === key)}
              phaseLabel={label}
              color={color}
              onTaskDrop={handleTaskDrop}
              allTasks={tasks}
            />
          ))}
        </div>
      )}
    </div>
  );
}
