"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useParams, useRouter } from "next/navigation";
import { CaretLeft, ListMagnifyingGlass } from "@phosphor-icons/react";
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
    setTasks,
    setAgents,
    backToProjects,
  } = useAppStore();
  const { connect, sendMessage } = useChat();
  const [tasksLoading, setTasksLoading] = useState(true);

  const projectName = params.id as string;
  const windowId = searchParams.get("window") || `web:s_${Date.now()}`;

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

  return (
    <div className="h-dvh flex flex-col bg-surface">
      {/* Top bar */}
      <header className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              backToProjects();
              router.push("/");
            }}
            className="p-1.5 hover:bg-surface-tertiary rounded-lg transition-colors text-text-secondary"
            aria-label="Back to projects"
          >
            <CaretLeft size={18} />
          </button>
          <span className="font-medium text-sm text-text-primary">
            {currentProject?.display_name || projectName}
          </span>
          <span className="text-xs text-text-muted font-mono hidden sm:inline">
            / {windowId.slice(0, 12)}...
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            {agents.map((a) => (
              <AgentAvatar key={a.id} agentId={a.id} name={a.name} size="sm" isMomo={a.is_momo} />
            ))}
          </div>
          <ThemeToggle />
        </div>
      </header>

      {/* Main area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          <ChatMessageList
            messages={messages}
            isStreaming={isStreaming}
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

          {/* Memory section in sidebar */}
          <div className="p-4 flex-1 overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
                Memory
              </h3>
              <button
                onClick={() => router.push(`/project/${projectName}/memory?window=${windowId}`)}
                className="text-[10px] text-accent hover:underline flex items-center gap-1"
              >
                <ListMagnifyingGlass size={12} />
                View all
              </button>
            </div>
            <p className="text-xs text-text-muted">
              Reflections and decisions appear here as agents work.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
