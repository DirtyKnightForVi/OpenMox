"use client";

import { useState, useCallback } from "react";
import { clsx } from "clsx";
import { TaskCard } from "./TaskCard";
import type { Task } from "@/lib/types";

interface PhaseColumnProps {
  phase: string;
  tasks: Task[];
  phaseLabel: string;
  color: string;
  onTaskDrop?: (taskId: string, fromPhase: string, toPhase: string) => void;
  allTasks: Task[];
}

export function PhaseColumn({ phase, tasks, phaseLabel, color, onTaskDrop, allTasks }: PhaseColumnProps) {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      try {
        const data = JSON.parse(e.dataTransfer.getData("text/plain"));
        if (data.phase !== phase) {
          onTaskDrop?.(data.taskId, data.phase, phase);
        }
      } catch {
        // ignore invalid drag data
      }
    },
    [phase, onTaskDrop],
  );

  // Check if any dependency is unblocked (predecessor done) — for highlighting
  const readyCount = tasks.filter((t) => {
    if (t.status !== "blocked" && t.status !== "pending") return false;
    return t.depends_on.every((depId) =>
      allTasks.find((at) => at.id === depId)?.status === "done",
    );
  }).length;

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={clsx(
        "flex flex-col gap-2 rounded-lg p-2 -mx-2 transition-colors",
        isDragOver && "bg-accent/5 ring-2 ring-accent/20",
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className={clsx("size-2 rounded-full", color)} />
        <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">{phaseLabel}</h4>
        <span className="text-[10px] text-text-muted ml-auto">{tasks.length}</span>
        {readyCount > 0 && (
          <span className="text-[10px] text-emerald-500 font-medium">{readyCount} ready</span>
        )}
      </div>
      <div className="space-y-2 min-h-[32px]">
        {tasks.length === 0 ? (
          <div
            className={clsx(
              "text-xs text-text-muted italic px-1 py-3 text-center rounded-lg border border-dashed",
              isDragOver ? "border-accent/30 text-accent" : "border-transparent",
            )}
          >
            {isDragOver ? "Drop here" : "No tasks yet"}
          </div>
        ) : (
          tasks.map((t) => <TaskCard key={t.id} task={t} />)
        )}
      </div>
    </div>
  );
}
