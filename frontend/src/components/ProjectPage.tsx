"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams, useParams, useRouter } from "next/navigation";
import { CaretLeft, PaperPlaneTilt, At } from "@phosphor-icons/react";
import { useAppStore } from "@/stores/app";
import { useChat } from "@/lib/useChat";
import { getDashboard, listAgents } from "@/lib/api";

const agentColors: Record<string, string> = {
  momo: "border-l-blue-400 bg-blue-50",
  "product-manager": "border-l-amber-400 bg-amber-50",
  "dev-manager": "border-l-indigo-400 bg-indigo-50",
  "arch-manager": "border-l-rose-400 bg-rose-50",
};

const agentInitials: Record<string, string> = {
  momo: "M",
  "product-manager": "P",
  "dev-manager": "D",
  "arch-manager": "A",
};

export default function ProjectPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { currentProject, messages, isStreaming, agents, tasks, setTasks, setAgents, backToProjects } = useAppStore();
  const { connect, sendMessage } = useChat();
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const projectName = params.id as string;
  const windowId = searchParams.get("window") || `web:s_${Date.now()}`;

  useEffect(() => {
    connect();
  }, [connect]);

  useEffect(() => {
    listAgents(projectName).then(setAgents).catch(() => {});
  }, [projectName, setAgents]);

  useEffect(() => {
    const interval = setInterval(() => {
      getDashboard(windowId).then((d) => setTasks(Object.values(d.phases).flat())).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [windowId, setTasks]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    sendMessage(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="h-dvh flex flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between px-4 py-2 border-b border-border bg-white shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={() => { backToProjects(); router.push("/"); }} className="p-1.5 hover:bg-muted rounded-lg transition-colors text-text-secondary">
            <CaretLeft size={18} />
          </button>
          <span className="font-medium text-sm">{currentProject?.display_name || projectName}</span>
          <span className="text-xs text-text-muted">/ {windowId.slice(0, 12)}...</span>
        </div>
        <div className="flex items-center gap-1">
          {agents.map((a) => (
            <button key={a.id} onClick={() => setInput((p) => `${p}@${a.id} `)} title={`@${a.id} — ${a.name}`}
              className={`size-7 rounded-full text-xs font-medium flex items-center justify-center ${agentColors[a.id] ? agentColors[a.id].split(" ").slice(-1)[0] : "bg-muted text-text-secondary"}`}>
              {agentInitials[a.id] || a.id[0].toUpperCase()}
            </button>
          ))}
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-text-muted text-sm">
                <p className="text-xs">Send a message to start collaborating</p>
                <p className="text-xs mt-1">Use @AgentName to address specific agents</p>
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}>
                {msg.sender === "user" ? (
                  <div className="max-w-[70%] rounded-2xl px-4 py-2.5 bg-accent text-white text-sm leading-relaxed">
                    {msg.text}
                  </div>
                ) : msg.sender === "system" ? (
                  <div className="max-w-[80%] text-xs text-text-muted italic text-center mx-auto">{msg.text}</div>
                ) : (
                  <div className={`max-w-[75%] rounded-xl px-4 py-2.5 text-sm leading-relaxed border border-border/50 ${agentColors[msg.sender] || "bg-white border-l-2 border-l-gray-300"}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`size-5 rounded-full text-[10px] font-medium flex items-center justify-center ${msg.sender === "momo" ? "bg-blue-200 text-blue-700" : "bg-gray-200 text-gray-600"}`}>
                        {agentInitials[msg.sender] || msg.sender[0].toUpperCase()}
                      </span>
                      <span className="text-xs font-medium text-text-secondary">{msg.sender}</span>
                    </div>
                    {msg.text || <span className="text-text-muted italic">thinking...</span>}
                  </div>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t border-border p-3 bg-white">
            <div className="flex items-center gap-2 bg-muted rounded-xl px-4 py-2.5 border border-border/50 focus-within:border-accent/50 transition-colors">
              <button className="text-text-muted hover:text-text-secondary transition-colors" title="Mention agent">
                <At size={18} />
              </button>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a message... @momo to start"
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-text-muted"
                disabled={isStreaming}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isStreaming}
                className="p-1.5 rounded-lg bg-accent text-white disabled:opacity-30 hover:bg-emerald-700 transition-colors"
              >
                <PaperPlaneTilt size={16} weight="fill" />
              </button>
            </div>
          </div>
        </div>

        {/* Right sidebar */}
        <aside className="w-72 sidebar-panel shrink-0 flex flex-col">
          {/* Tasks */}
          <div className="p-4 border-b border-border">
            <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">Tasks</h3>
            <div className="space-y-2">
              {tasks.length === 0 && <p className="text-xs text-text-muted">No tasks yet</p>}
              {["research", "development", "review"].map((phase) => {
                const phaseTasks = tasks.filter((t) => t.phase === phase);
                if (phaseTasks.length === 0) return null;
                return (
                  <div key={phase}>
                    <div className="text-[10px] font-medium text-text-muted uppercase mb-1">{phase}</div>
                    {phaseTasks.map((t) => (
                      <div key={t.id} className="flex items-center gap-2 py-1.5 px-2 rounded-md hover:bg-muted transition-colors">
                        <div className={`size-2 rounded-full shrink-0 ${
                          t.status === "done" ? "bg-emerald-500" :
                          t.status === "in_progress" ? "bg-amber-400" :
                          t.status === "blocked" ? "bg-red-400" : "bg-gray-300"
                        }`} />
                        <span className="text-xs truncate flex-1">{t.title}</span>
                        <span className="text-[10px] text-text-muted shrink-0">{t.owner.split("-")[0]}</span>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Memory */}
          <div className="p-4 flex-1 overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Memory</h3>
              <button
                onClick={() => router.push(`/project/${projectName}/memory?window=${windowId}`)}
                className="text-[10px] text-accent hover:underline"
              >
                View all
              </button>
            </div>
            <p className="text-xs text-text-muted">Reflections appear here as agents work.</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
