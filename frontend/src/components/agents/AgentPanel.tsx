"use client";

import { useRouter } from "next/navigation";
import { clsx } from "clsx";
import { Plus, Brain, Wrench } from "@phosphor-icons/react";
import { AgentAvatar } from "./AgentAvatar";
import { getAgentColor } from "./AgentColorMap";
import { useAppStore } from "@/stores/app";
import type { Agent, Task, WorkDetail } from "@/lib/types";

interface AgentPanelProps {
  agents: Agent[];
  projectName: string;
  windowId: string;
}

/** Filter tasks owned by this agent, sorted: in_progress → blocked → pending */
function tasksForAgent(tasks: Task[], agentId: string): Task[] {
  return tasks
    .filter((t) => t.owner === agentId)
    .sort((a, b) => {
      const order: Record<string, number> = { in_progress: 0, blocked: 1, pending: 2, done: 3 };
      return (order[a.status] ?? 9) - (order[b.status] ?? 9);
    });
}

/** Render the agent's current activity from WorkDetail */
function ActivitySummary({ work }: { work?: WorkDetail }) {
  if (!work || !work.currentTask) return null;
  return (
    <div className="mt-1.5 text-[10px] text-text-muted truncate flex items-center gap-1">
      <span className="size-1 rounded-full bg-amber-400 animate-pulse shrink-0" />
      <span className="truncate">{work.currentTask}</span>
    </div>
  );
}

/** Render recent tool calls as tiny pills */
function ToolCallPills({ work }: { work?: WorkDetail }) {
  if (!work || work.toolCalls.length === 0) return null;
  // Show the last 3 tool calls
  const recent = work.toolCalls.slice(-3);
  return (
    <div className="mt-1.5 flex flex-wrap gap-1">
      {recent.map((tc, i) => {
        const isError = tc.state === "error" || tc.state === "denied";
        const isSuccess = tc.state === "success";
        return (
          <span
            key={i}
            className={clsx(
              "inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-medium leading-none",
              isError
                ? "bg-red-100 text-red-600 dark:bg-red-900/20 dark:text-red-400"
                : isSuccess
                  ? "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400"
                  : "bg-blue-100 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400",
            )}
            title={tc.name}
          >
            <Wrench size={8} weight="bold" />
            {tc.name.length > 14 ? tc.name.slice(0, 14) + "…" : tc.name}
          </span>
        );
      })}
    </div>
  );
}

export function AgentPanel({ agents, projectName, windowId }: AgentPanelProps) {
  const router = useRouter();
  const { agentStatus, agentWorkDetail, tasks } = useAppStore();

  return (
    <div className="p-4 flex-1 overflow-y-auto border-t border-border">
      {/* Section header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
          Agents
        </h3>
        <button
          onClick={() => router.push(`/project/${projectName}/agents?window=${windowId}`)}
          className="text-[10px] text-accent hover:underline flex items-center gap-1"
        >
          <Plus size={12} weight="bold" />
          Add
        </button>
      </div>

      {/* Agent list */}
      <div className="space-y-2">
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            status={agentStatus[agent.id] || "idle"}
            work={agentWorkDetail[agent.id]}
            agentTasks={tasksForAgent(tasks, agent.id)}
            onMemoryClick={() =>
              router.push(`/project/${projectName}/memory?window=${windowId}&agent=${agent.id}`)
            }
          />
        ))}
      </div>

      {/* Empty state */}
      {agents.length === 0 && (
        <div className="text-center py-6">
          <p className="text-xs text-text-muted mb-1">No agents yet</p>
          <p className="text-[10px] text-text-muted">Add a colleague to get started</p>
        </div>
      )}
    </div>
  );
}

// ── Sub-component: individual agent card ──

interface AgentCardProps {
  agent: Agent;
  status: "idle" | "busy";
  work?: WorkDetail;
  agentTasks: Task[];
  onMemoryClick: () => void;
}

function AgentCard({ agent, status, work, agentTasks, onMemoryClick }: AgentCardProps) {
  const isBusy = status === "busy";
  const currentTask = agentTasks.find((t) => t.status === "in_progress");
  const color = getAgentColor(agent.id);

  return (
    <div
      className={clsx(
        "rounded-xl border px-3 py-2.5 transition-all",
        isBusy
          ? "border-amber-400/40 bg-amber-50/40 dark:bg-amber-900/10"
          : "border-border bg-surface-tertiary/50 hover:bg-surface-tertiary/80",
      )}
    >
      {/* Row: avatar + name/status + actions */}
      <div className="flex items-start gap-2.5">
        {/* Avatar with status dot */}
        <div className="relative shrink-0">
          <AgentAvatar agentId={agent.id} name={agent.name} size="sm" isMomo={agent.is_momo} />
          <span
            className={clsx(
              "absolute -bottom-0.5 -right-0.5 size-2.5 rounded-full border-2 border-surface",
              isBusy ? "bg-amber-400 animate-pulse" : "bg-emerald-500",
            )}
          />
        </div>

        {/* Name + description + capabilities */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-text-primary truncate">
              {agent.name || agent.id}
            </span>
            <span className={clsx("text-[10px] font-medium", isBusy ? "text-amber-500" : "text-emerald-500")}>
              {isBusy ? "Working" : "Idle"}
            </span>
          </div>

          {/* Description */}
          {agent.description && (
            <p className="text-[10px] text-text-muted mt-0.5 line-clamp-2 leading-relaxed">
              {agent.description}
            </p>
          )}

          {/* Capabilities badges */}
          {agent.capabilities && agent.capabilities.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {agent.capabilities.slice(0, 3).map((cap) => (
                <span
                  key={cap}
                  className={clsx(
                    "px-1.5 py-[1px] rounded text-[9px] font-medium leading-tight",
                    color.bg,
                    color.text,
                  )}
                >
                  {cap}
                </span>
              ))}
              {agent.capabilities.length > 3 && (
                <span className="text-[9px] text-text-muted">+{agent.capabilities.length - 3}</span>
              )}
            </div>
          )}

          {/* Activity: current task from work detail */}
          <ActivitySummary work={work} />

          {/* Tool call pills */}
          <ToolCallPills work={work} />
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-0.5 shrink-0 pt-0.5">
          <button
            onClick={onMemoryClick}
            className="p-1 rounded text-text-muted hover:text-accent hover:bg-accent/5 transition-colors"
            title="View memory"
            aria-label="View memory"
          >
            <Brain size={14} />
          </button>
        </div>
      </div>

      {/* Current task from dashboard (if any) */}
      {currentTask && (
        <div className="mt-1.5 pl-[34px]">
          <div className="flex items-center gap-1.5 text-[10px] text-text-muted bg-surface-tertiary/60 rounded-lg px-2 py-1">
            <span className="size-1.5 rounded-full bg-amber-400 shrink-0" />
            <span className="truncate">{currentTask.title}</span>
          </div>
        </div>
      )}

      {/* Extra tasks count */}
      {agentTasks.length > 1 && (
        <div className="mt-1 pl-[34px] text-[10px] text-text-muted">
          {agentTasks.length - 1} more task{agentTasks.length - 1 > 1 ? "s" : ""}
        </div>
      )}
    </div>
  );
}
