"use client";

import { useState, useEffect, useRef } from "react";
import { clsx } from "clsx";
import { useAppStore } from "@/stores/app";
import type { TaskProgressEvent } from "@/lib/types";

/**
 * Collapsible task-progress panel — shows worker internal events
 * (thinking, tool calls, results) in real time, grouped by worker agent.
 *
 * Data source: ``task_progress`` CustomEvents published by
 * ``TaskPanelProjector`` (backend) and delivered through the
 * window WebSocket stream.
 */
export function TaskProgressPanel() {
  const taskProgress = useAppStore((s) => s.taskProgress);
  const [expandedWorkers, setExpandedWorkers] = useState<Set<string>>(new Set());
  const scrollRefs = useRef<Record<string, HTMLDivElement | null>>({});

  // Auto-expand new workers when they first produce events
  const prevKeysRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    const currentKeys = new Set(Object.keys(taskProgress));
    for (const key of currentKeys) {
      if (!prevKeysRef.current.has(key) && taskProgress[key]?.length > 0) {
        setExpandedWorkers((prev) => new Set(prev).add(key));
      }
    }
    prevKeysRef.current = currentKeys;
  }, [taskProgress]);

  // Auto-scroll to bottom when expanded and receiving new events
  useEffect(() => {
    for (const [key, events] of Object.entries(taskProgress)) {
      if (expandedWorkers.has(key) && events.length > 0) {
        const el = scrollRefs.current[key];
        if (el) {
          el.scrollTop = el.scrollHeight;
        }
      }
    }
  }, [taskProgress, expandedWorkers]);

  const workerKeys = Object.keys(taskProgress);
  if (workerKeys.length === 0) return null;

  return (
    <div className="border-t border-border">
      <div className="px-4 py-2">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
          Work Progress
        </h3>
        {workerKeys.map((workerId) => {
          const events = taskProgress[workerId] || [];
          if (events.length === 0) return null;
          const workerName = events[0]?.worker_agent_name || workerId;
          const isExpanded = expandedWorkers.has(workerId);
          const lastEvent = events[events.length - 1];

          return (
            <WorkerProgressCard
              key={workerId}
              workerId={workerId}
              workerName={workerName}
              events={events}
              isExpanded={isExpanded}
              lastEvent={lastEvent}
              onToggle={() =>
                setExpandedWorkers((prev) => {
                  const next = new Set(prev);
                  if (next.has(workerId)) next.delete(workerId);
                  else next.add(workerId);
                  return next;
                })
              }
              scrollRef={(el) => (scrollRefs.current[workerId] = el)}
            />
          );
        })}
      </div>
    </div>
  );
}

// ── Per-worker card ──────────────────────────────

function WorkerProgressCard({
  workerId,
  workerName,
  events,
  isExpanded,
  lastEvent,
  onToggle,
  scrollRef,
}: {
  workerId: string;
  workerName: string;
  events: TaskProgressEvent[];
  isExpanded: boolean;
  lastEvent: TaskProgressEvent | undefined;
  onToggle: () => void;
  scrollRef: (el: HTMLDivElement | null) => void;
}) {
  const statusDot = getStatusDot(lastEvent);

  return (
    <div className="mb-2 rounded-lg border border-border overflow-hidden">
      {/* Header — click to expand/collapse */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-surface-secondary transition-colors"
      >
        <span className={clsx("size-2 rounded-full shrink-0", statusDot)} />
        <span className="text-xs font-medium text-text-primary truncate flex-1">
          {workerName}
        </span>
        <span className="text-[10px] text-text-muted">{events.length} events</span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className={clsx(
            "text-text-muted transition-transform shrink-0",
            isExpanded && "rotate-180",
          )}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {/* Body — streamed event log */}
      {isExpanded && (
        <div
          ref={scrollRef}
          className="max-h-48 overflow-y-auto border-t border-border bg-surface-tertiary/30"
        >
          <div className="px-3 py-1.5 font-mono text-[11px] leading-relaxed">
            {events.map((ev, i) => (
              <ProgressEventLine key={`${ev.reply_id}-${ev.event_seq}-${i}`} event={ev} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Single event line ───────────────────────────

function ProgressEventLine({ event }: { event: TaskProgressEvent }) {
  if (event.delta !== undefined) {
    // Thinking block delta
    return (
      <div className="text-text-muted italic py-0.5">
        <span className="text-[10px] text-text-muted/50 mr-1">
          {formatTime(event.timestamp)}
        </span>
        {event.delta.slice(0, 200)}
      </div>
    );
  }

  if (event.thinking_started) {
    return (
      <div className="text-text-muted/50 text-[10px] py-0.5">
        ── thinking start ──
      </div>
    );
  }

  if (event.thinking_ended) {
    return (
      <div className="text-text-muted/50 text-[10px] py-0.5">
        ── thinking end ──
      </div>
    );
  }

  if (event.tool_name) {
    return (
      <div className="text-amber-600 dark:text-amber-400 py-0.5">
        <span className="text-[10px] text-text-muted/50 mr-1">
          {formatTime(event.timestamp)}
        </span>
        🔧 {event.tool_name}
        {event.tool_input != null && (
          <span className="text-text-muted/70 ml-1">
            {truncateInput(event.tool_input)}
          </span>
        )}
      </div>
    );
  }

  if (event.tool_state) {
    const isSuccess = event.tool_state === "success";
    return (
      <div
        className={clsx(
          "py-0.5",
          isSuccess ? "text-emerald-600 dark:text-emerald-400" : "text-red-500",
        )}
      >
        <span className="text-[10px] text-text-muted/50 mr-1">
          {formatTime(event.timestamp)}
        </span>
        {isSuccess ? "✅" : "❌"} {event.tool_name || "tool"}
        {event.tool_output && (
          <span className="text-text-muted/70 ml-1">
            {event.tool_output.slice(0, 80)}
          </span>
        )}
      </div>
    );
  }

  if (event.tool_result_started) {
    return (
      <div className="text-text-muted/50 text-[10px] py-0.5">
        ── result start ──
      </div>
    );
  }

  if (event.summary) {
    return (
      <div className="text-text-primary py-1 border-t border-border/50 mt-0.5">
        <span className="text-[10px] text-text-muted/50 mr-1">
          {formatTime(event.timestamp)}
        </span>
        📝 {event.summary.slice(0, 300)}
      </div>
    );
  }

  return null;
}

// ── Helpers ─────────────────────────────────────

function getStatusDot(lastEvent: TaskProgressEvent | undefined): string {
  if (!lastEvent) return "bg-gray-300";
  if (lastEvent.event_type === "TextBlockEndEvent") return "bg-emerald-500"; // done
  if (lastEvent.tool_state === "error") return "bg-red-400";
  return "bg-amber-400 animate-pulse"; // working
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function truncateInput(input: unknown): string {
  try {
    const s = typeof input === "string" ? input : JSON.stringify(input);
    return s.length > 60 ? s.slice(0, 57) + "..." : s;
  } catch {
    return "";
  }
}
