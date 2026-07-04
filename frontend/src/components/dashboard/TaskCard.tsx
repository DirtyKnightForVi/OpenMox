"use client";

import { useCallback, useRef, useState } from "react";
import { clsx } from "clsx";
import { CaretDown } from "@phosphor-icons/react";
import { getAgentColor } from "@/components/agents/AgentColorMap";
import { Badge } from "@/components/ui/Badge";
import { TaskDetailPanel } from "./TaskDetailPanel";
import type { Task } from "@/lib/types";

interface TaskCardProps {
  task: Task;
  onDragStart?: (taskId: string, phase: string) => void;
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

export function TaskCard({ task, onDragStart }: TaskCardProps) {
  const status = statusConfig[task.status] || statusConfig.pending;
  const agentColor = getAgentColor(task.owner);
  const dragRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);

  const handleDragStart = useCallback(
    (e: React.DragEvent) => {
      e.dataTransfer.setData("text/plain", JSON.stringify({ taskId: task.id, phase: task.phase }));
      e.dataTransfer.effectAllowed = "move";
      if (dragRef.current) {
        dragRef.current.style.opacity = "0.5";
      }
      onDragStart?.(task.id, task.phase);
    },
    [task.id, task.phase, onDragStart],
  );

  const handleDragEnd = useCallback(() => {
    if (dragRef.current) {
      dragRef.current.style.opacity = "1";
    }
  }, []);

  return (
    <div
      ref={dragRef}
      draggable
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      className={clsx(
        "rounded-lg border px-3 py-2.5 transition-all cursor-grab active:cursor-grabbing",
        "hover:shadow-sm hover:border-accent/30",
        status.color,
      )}
    >
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

      {/* Communication budget progress bar */}
      {task.communication_budget !== undefined && task.communication_budget > 0 && (
        <div className="mt-2">
          <div className="flex items-center justify-between text-[10px] text-text-muted mb-0.5">
            <span>Budget</span>
            <span>{Math.round(task.communication_budget * 100)}%</span>
          </div>
          <div className="h-1 bg-surface-tertiary rounded-full overflow-hidden">
            <div
              className={clsx(
                "h-full rounded-full transition-all",
                task.communication_budget > 0.7
                  ? "bg-amber-400"
                  : task.communication_budget > 0.4
                    ? "bg-emerald-400"
                    : "bg-emerald-500",
              )}
              style={{ width: `${Math.min(task.communication_budget * 100, 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Depends-on indicator */}
      {task.depends_on.length > 0 && (
        <div className="mt-1.5 flex items-center gap-1 text-[10px] text-text-muted">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M5 12h14M12 5l7 7-7 7" />
          </svg>
          <span>depends on {task.depends_on.length}</span>
        </div>
      )}

      {/* Expand/collapse toggle */}
      {task.status === "in_progress" && (
        <button
          onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
          className="mt-2 flex items-center gap-1 text-[10px] text-text-muted hover:text-text-secondary transition-colors w-full"
        >
          <CaretDown
            size={12}
            className={clsx("transition-transform", expanded ? "rotate-0" : "-rotate-90")}
          />
          <span>{expanded ? "Hide progress" : "View progress"}</span>
        </button>
      )}

      {/* Expandable detail panel */}
      <TaskDetailPanel task={task} isOpen={expanded} />
    </div>
  );
}
