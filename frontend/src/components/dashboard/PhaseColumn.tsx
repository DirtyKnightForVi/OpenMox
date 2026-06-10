"use client";

import { clsx } from "clsx";
import { TaskCard } from "./TaskCard";
import type { Task } from "@/lib/types";

interface PhaseColumnProps {
  phase: string;
  tasks: Task[];
  phaseLabel: string;
  color: string;
}

export function PhaseColumn({ phase, tasks, phaseLabel, color }: PhaseColumnProps) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 mb-1">
        <span className={clsx("size-2 rounded-full", color)} />
        <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">{phaseLabel}</h4>
        <span className="text-[10px] text-text-muted ml-auto">{tasks.length}</span>
      </div>
      <div className="space-y-2">
        {tasks.length === 0 ? (
          <p className="text-xs text-text-muted italic px-1">No tasks yet</p>
        ) : (
          tasks.map((t) => <TaskCard key={t.id} task={t} />)
        )}
      </div>
    </div>
  );
}
