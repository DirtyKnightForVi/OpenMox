"use client";

import { useState, useEffect } from "react";
import { clsx } from "clsx";
import { useSearchParams } from "next/navigation";
import { useAppStore } from "@/stores/app";
import type { Task, TaskProgressEvent } from "@/lib/types";

interface TaskDetailPanelProps {
  task: Task;
  isOpen: boolean;
}

/**
 * Expandable detail panel inside a task card.
 * Shows:
 *   1. Execution plan (TaskContext from Redis — head/middle/tail queue)
 *   2. Real-time work stream (SSE events from taskProgress store)
 */
export function TaskDetailPanel({ task, isOpen }: TaskDetailPanelProps) {
  const searchParams = useSearchParams();
  const storeWindowId = useAppStore((s) => s.currentWindowId);
  const taskProgress = useAppStore((s) => s.taskProgress);
  const storeProjectPath = useAppStore((s) => s.currentProjectPath);

  // Resolve windowId: store first, URL fallback for old projects
  const currentWindowId = storeWindowId || searchParams.get("window") || "";
  // Resolve projectPath: store first, "." fallback
  const currentProjectPath = storeProjectPath || ".";

  const [planTasks, setPlanTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  // Fetch TaskContext on open
  useEffect(() => {
    if (!isOpen || !task.owner || !currentWindowId) return;
    setLoading(true);
    fetch(
      `http://localhost:8000/api/dashboard/tasks/${encodeURIComponent(task.owner)}?window_id=${encodeURIComponent(currentWindowId)}&project_path=${encodeURIComponent(currentProjectPath)}`
    )
      .then((r) => r.json())
      .then((data) => setPlanTasks(data.tasks || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [isOpen, task.owner, currentWindowId, currentProjectPath]);

  // Get SSE events for this task's owner
  const workerEvents: TaskProgressEvent[] = taskProgress[task.owner] || [];
  const recentEvents = workerEvents.slice(-30);

  if (!isOpen) return null;

  return (
    <div className="mt-2 border-t border-border pt-2">
      {/* ── Execution Plan ── */}
      {loading ? (
        <div className="text-[10px] text-text-muted py-1">Loading plan...</div>
      ) : planTasks.length > 0 ? (
        <div className="mb-2">
          <div className="text-[10px] font-semibold text-text-secondary uppercase mb-1">Execution Plan</div>
          <div className="space-y-0.5">
            {planTasks.map((t: any) => (
              <div key={t.id} className="flex items-center gap-1.5 text-[10px]">
                <span>
                  {t.state === "completed" ? "✅" : t.state === "in_progress" ? "🟡" : "⏳"}
                </span>
                <span className={clsx(
                  "truncate",
                  t.state === "completed" ? "text-text-muted line-through" : "text-text-primary"
                )}>
                  {t.subject}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* ── Real-time work stream ── */}
      {recentEvents.length > 0 && (
        <div>
          <div className="text-[10px] font-semibold text-text-secondary uppercase mb-1">
            Live Stream ({workerEvents.length} events)
          </div>
          <div className="max-h-36 overflow-y-auto font-mono text-[10px] leading-relaxed bg-surface-tertiary/40 rounded p-1.5">
            {recentEvents.map((ev, i) => (
              <ProgressLine key={`${ev.reply_id}-${ev.event_seq}-${i}`} event={ev} />
            ))}
          </div>
        </div>
      )}

      {planTasks.length === 0 && recentEvents.length === 0 && !loading && (
        <div className="text-[10px] text-text-muted py-1">No progress data yet. Worker may not have started.</div>
      )}
    </div>
  );
}

// ── Single progress line ─────────────────────

function ProgressLine({ event }: { event: TaskProgressEvent }) {
  const time = new Date(event.timestamp).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  if (event.delta !== undefined) {
    return <div className="text-text-muted italic">💭 {event.delta.slice(0, 120)}</div>;
  }
  if (event.thinking_started) return <div className="text-text-muted/50">── thinking ──</div>;
  if (event.thinking_ended) return <div className="text-text-muted/50">── thought ──</div>;
  if (event.tool_name) {
    return (
      <div className="text-amber-600 dark:text-amber-400">
        <span className="text-text-muted/50">{time}</span> 🔧 {event.tool_name}
      </div>
    );
  }
  if (event.tool_state) {
    const ok = event.tool_state === "success";
    return (
      <div className={ok ? "text-emerald-600" : "text-red-500"}>
        <span className="text-text-muted/50">{time}</span> {ok ? "✅" : "❌"} {event.tool_name || "tool"}
        {event.tool_output ? ` — ${event.tool_output.slice(0, 60)}` : ""}
      </div>
    );
  }
  if (event.summary) {
    return <div className="text-text-primary border-t border-border/30 pt-0.5">📝 {event.summary.slice(0, 200)}</div>;
  }
  return null;
}
