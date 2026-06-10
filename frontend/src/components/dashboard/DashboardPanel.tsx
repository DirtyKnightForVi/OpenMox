"use client";

import { TaskSkeleton } from "@/components/ui/Skeleton";
import { PhaseColumn } from "./PhaseColumn";
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
  if (isLoading) {
    return (
      <div className="p-4">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">Tasks</h3>
        <TaskSkeleton />
      </div>
    );
  }

  return (
    <div className="p-4 border-b border-border">
      <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">Tasks</h3>
      <div className="space-y-4">
        {PHASE_CONFIG.map(({ key, label, color }) => (
          <PhaseColumn
            key={key}
            phase={key}
            tasks={tasks.filter((t) => t.phase === key)}
            phaseLabel={label}
            color={color}
          />
        ))}
      </div>
    </div>
  );
}
