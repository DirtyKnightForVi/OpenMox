"use client";

import { useEffect, useState, useMemo, useRef } from "react";
import { useSearchParams, useParams, useRouter } from "next/navigation";
import { clsx } from "clsx";
import { useAppStore } from "@/stores/app";
import { useChat } from "@/lib/useChat";
import { getDashboard, listAgents, getMessages } from "@/lib/api";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { AgentAvatar } from "@/components/agents/AgentAvatar";
import { AgentPanel } from "@/components/agents/AgentPanel";
import { ChatMessageList } from "@/components/chat/ChatMessageList";
import { ChatInput } from "@/components/chat/ChatInput";
import { DashboardPanel } from "@/components/dashboard/DashboardPanel";

export default function ProjectPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const {
    projects,
    currentProject,
    messages,
    isStreaming,
    agents,
    tasks,
    agentStatus,
    wsConnected,
    setTasks,
    setAgents,
    setCurrentProject,
    setCurrentProjectPath,
    addWindowTab,
    setActiveWindowId,
  } = useAppStore();
  const { connect, sendMessage } = useChat();
  const [tasksLoading, setTasksLoading] = useState(true);

  const projectName = params.id as string;
  // Resolve project_path from the store — fall back to projects list lookup
  const projectPath = useMemo(() => {
    if (currentProject?.full_path) return currentProject.full_path;
    // Try to find by name from the stored projects list
    const found = projects.find(
      (p: { name: string }) => p.name === projectName
    );
    return found?.full_path || ".";
  }, [currentProject, projectName, projects]);

  // Sync resolved projectPath to the store so useChat can use it
  useEffect(() => {
    if (projectPath && projectPath !== ".") {
      setCurrentProjectPath(projectPath);
    }
  }, [projectPath, setCurrentProjectPath]);

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

  // Load message history on page load / window switch
  useEffect(() => {
    if (!windowId || windowId === "new") return;
    getMessages(windowId)
      .then((res) => {
        if (res.messages) {
          const msgs = res.messages.map((m: any) => ({
            id: `hist-${m.id}`,
            sender: m.speaker_type === "human" ? "user" : (m.speaker_id || "assistant"),
            text: m.content || "",
            timestamp: (m.timestamp || 0) * 1000,
            events: [],
          }));
          // Replace, don't append — history is the full timeline
          useAppStore.setState((s) => ({ messages: msgs }));
        }
      })
      .catch(() => {});
  }, [windowId]);

  // Ensure we have the projects list on page load (e.g., direct URL navigation)
  const { setProjects } = useAppStore();
  useEffect(() => {
    if (projects.length === 0) {
      import("@/lib/api").then(({ listProjects }) =>
        listProjects().then(setProjects).catch(() => {})
      );
    }
  }, [projects.length, setProjects]);

  useEffect(() => {
    connect();
  }, [connect]);

  useEffect(() => {
    listAgents(projectName).then(setAgents).catch(() => {});
  }, [projectName, setAgents]);

  // Poll dashboard every 30s (reduced from 5s to avoid request flood).
  // Use a ref to track active state — prevents duplicate intervals from
  // React StrictMode double-mount.
  const dashIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    const fetchDash = () => {
      getDashboard(windowId, projectPath)
        .then((d) => setTasks(Object.values(d.phases).flat()))
        .catch(() => {})
        .finally(() => setTasksLoading(false));
    };
    setTasksLoading(true);
    fetchDash();
    dashIntervalRef.current = setInterval(fetchDash, 30_000);
    return () => {
      if (dashIntervalRef.current) {
        clearInterval(dashIntervalRef.current);
        dashIntervalRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [windowId, projectPath]);

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
            const detail = useAppStore.getState().agentWorkDetail[a.id];
            const currentTool = detail?.currentTask;
            const tooltip = currentTool
              ? `${a.name || a.id} — ${currentTool}`
              : `${a.name || a.id} — ${status === "busy" ? "Working" : "Idle"}`;
            return (
              <button
                key={a.id}
                onClick={() => router.push(`/project/${projectName}/memory?window=${windowId}&agent=${a.id}`)}
                className="relative group"
                title={tooltip}
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
                {/* Work detail tooltip on hover */}
                {currentTool && (
                  <div className="absolute top-full mt-1.5 left-1/2 -translate-x-1/2 z-20 hidden group-hover:block">
                    <div className="bg-surface-tertiary/95 backdrop-blur-sm border border-border text-[10px] text-text-secondary rounded-lg px-2 py-1 whitespace-nowrap shadow-lg">
                      {currentTool}
                    </div>
                  </div>
                )}
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

          {/* Agent panel — capability cards + status visualization */}
          <AgentPanel
            agents={agents}
            projectName={projectName}
            windowId={windowId}
          />
        </aside>
      </div>
    </div>
  );
}
