"use client";

import { clsx } from "clsx";
import { getAgentColor } from "@/components/agents/AgentColorMap";
import { Badge } from "@/components/ui/Badge";
import type { Task } from "@/lib/types";

interface TaskCardProps {
  task: Task;
}

const statusConfig: Record<string, { label: string; color: string; dot: string }> = {
  done: { label: "Done", color: "border-emerald-500/20 bg-emerald-50/50 dark:bg-emerald-900/10", dot: "bg-emerald-500" },
  in_progress: { label: "In Progress", color: "border-amber-500/20 bg-amber-50/50 dark:bg-amber-900/10", dot: "bg-amber-400" },
  blocked: { label: "Blocked", color: "border-red-500/20 bg-red-50/50 dark:bg-red-900/10", dot: "bg-red-400" },
  pending: { label: "Pending", color: "border-border", dot: "bg-gray-300 dark:bg-gray-600" },
};

const phaseLabels: Record<string, string> = {
  research: "Research",
  development: "Development",
  review: "Review",
  delivery: "Delivery",
};

export function TaskCard({ task }: TaskCardProps) {
  const status = statusConfig[task.status] || statusConfig.pending;
  const agentColor = getAgentColor(task.owner);

  return (
    <div className={clsx("rounded-lg border px-3 py-2.5 transition-colors", status.color)}>
      <div className="flex items-start gap-2">
        <span className={clsx("size-2 rounded-full mt-1 shrink-0", status.dot)} />
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-text-primary truncate">{task.title}</p>
          {task.description && (
            <p className="text-[11px] text-text-muted mt-0.5 line-clamp-2">{task.description}</p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 mt-1.5">
        <Badge variant="default">{phaseLabels[task.phase] || task.phase}</Badge>
        <span className={clsx("text-[10px] px-1.5 py-0.5 rounded font-medium", agentColor.bg, agentColor.text)}>
          {task.owner}
        </span>
      </div>
    </div>
  );
}
