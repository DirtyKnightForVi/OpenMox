"use client";

import { useEffect, useState, useMemo, useRef } from "react";
import { useSearchParams, useParams, useRouter } from "next/navigation";
import { Plus } from "@phosphor-icons/react";
import { clsx } from "clsx";
import { useAppStore } from "@/stores/app";
import { useChat } from "@/lib/useChat";
import { getDashboard, listAgents } from "@/lib/api";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { AgentAvatar } from "@/components/agents/AgentAvatar";
import { ChatMessageList } from "@/components/chat/ChatMessageList";
import { ChatInput } from "@/components/chat/ChatInput";
import { DashboardPanel } from "@/components/dashboard/DashboardPanel";

export default function ProjectPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const {
    currentProject,
    messages,
    isStreaming,
    agents,
    tasks,
    agentStatus,
    wsConnected,
    setTasks,
    setAgents,
    addWindowTab,
    setActiveWindowId,
  } = useAppStore();
  const { connect, sendMessage } = useChat();
  const [tasksLoading, setTasksLoading] = useState(true);

  const projectName = params.id as string;
  // Stable windowId: use URL param when present, otherwise generate once
  const fallbackRef = useRef<string | null>(null);
  const windowId = useMemo(() => {
    const fromUrl = searchParams.get("window");
    if (fromUrl) return fromUrl;
    if (!fallbackRef.current) {
      fallbackRef.current = `web:s_${Date.now()}`;
    }
    return fallbackRef.current;
  }, [searchParams]);

  useEffect(() => {
    connect();
  }, [connect]);

  useEffect(() => {
    listAgents(projectName).then(setAgents).catch(() => {});
  }, [projectName, setAgents]);

  useEffect(() => {
    setTasksLoading(true);
    getDashboard(windowId)
      .then((d) => setTasks(Object.values(d.phases).flat()))
      .catch(() => {})
      .finally(() => setTasksLoading(false));

    const interval = setInterval(() => {
      getDashboard(windowId)
        .then((d) => setTasks(Object.values(d.phases).flat()))
        .catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [windowId, setTasks]);

  // Register the current window as a tab, and ensure currentWindowId is synced
  // to the store (critical: sendMessage in useChat relies on store.currentWindowId)
  useEffect(() => {
    addWindowTab({ id: windowId, label: currentProject?.display_name || projectName, projectName });
    setActiveWindowId(windowId);

    // If store lost currentWindowId (page refresh / sidebar nav without ?window=),
    // restore it so sendMessage doesn't silently drop messages
    const state = useAppStore.getState();
    if (!state.currentWindowId) {
      useAppStore.setState({ currentWindowId: windowId });
    }
  }, [windowId, projectName, currentProject, addWindowTab, setActiveWindowId]);

  return (
    <div className="flex flex-col flex-1 min-h-0 bg-surface">
      {/* Slim top bar */}
      <header className="flex items-center justify-between px-4 py-1.5 border-b border-border bg-surface shrink-0">
        <div className="flex items-center gap-2">
          {/* WS Connection indicator */}
          <span
            className={clsx(
              "size-1.5 rounded-full shrink-0",
              wsConnected ? "bg-emerald-500" : "bg-red-400",
            )}
            title={wsConnected ? "Connected" : "Disconnected"}
          />
          <span className="text-xs text-text-muted font-mono">
            {currentProject?.display_name || projectName}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {agents.map((a) => {
            const status = agentStatus[a.id] || "idle";
            return (
              <button
                key={a.id}
                onClick={() => router.push(`/project/${projectName}/memory?window=${windowId}&agent=${a.id}`)}
                className="relative"
                title={`${a.name || a.id} — ${status === "busy" ? "Working" : "Idle"}`}
              >
                <AgentAvatar agentId={a.id} name={a.name} size="sm" isMomo={a.is_momo} />
                {/* Busy indicator dot */}
                <span
                  className={clsx(
                    "absolute -top-0.5 -right-0.5 size-2.5 rounded-full border-2 border-surface",
                    status === "busy"
                      ? "bg-amber-400 animate-pulse"
                      : "bg-emerald-500",
                  )}
                />
              </button>
            );
          })}
          <ThemeToggle />
        </div>
      </header>

      {/* Main content flex */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          <ChatMessageList
            messages={messages}
            isStreaming={isStreaming}
            wsConnected={wsConnected}
          />
          <ChatInput
            agents={agents}
            isStreaming={isStreaming}
            onSend={sendMessage}
          />
        </div>

        {/* Right sidebar */}
        <aside className="w-72 sidebar-panel shrink-0 hidden lg:flex lg:flex-col">
          <DashboardPanel tasks={tasks} isLoading={tasksLoading} />

          {/* Agent panel */}
          <div className="p-4 flex-1 overflow-y-auto border-t border-border">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
                Agents
              </h3>
              <button
                onClick={() => router.push(`/project/${projectName}/agents?window=${windowId}`)}
                className="text-[10px] text-accent hover:underline flex items-center gap-1"
              >
                <Plus size={12} />
                Manage
              </button>
            </div>

            <div className="space-y-2">
              {agents.map((a) => (
                <div
                  key={a.id}
                  className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg bg-surface-tertiary/50"
                >
                  <div className="relative">
                    <AgentAvatar agentId={a.id} name={a.name} size="sm" isMomo={a.is_momo} />
                    <span
                      className={clsx(
                        "absolute -bottom-0.5 -right-0.5 size-2 rounded-full border border-surface",
                        (agentStatus[a.id] || "idle") === "busy"
                          ? "bg-amber-400 animate-pulse"
                          : "bg-emerald-500",
                      )}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-text-primary truncate">
                      {a.name || a.id}
                    </div>
                    <div className="text-[10px] text-text-muted">
                      {(agentStatus[a.id] || "idle") === "busy" ? "Working..." : "Idle"}
                    </div>
                  </div>
                  <button
                    onClick={() =>
                      router.push(
                        `/project/${projectName}/memory?window=${windowId}&agent=${a.id}`,
                      )
                    }
                    className="text-[10px] text-accent hover:underline shrink-0"
                  >
                    Memory
                  </button>
                </div>
              ))}
            </div>

            {agents.length === 0 && (
              <p className="text-xs text-text-muted text-center py-4">
                No agents yet. Add one in Team.
              </p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
