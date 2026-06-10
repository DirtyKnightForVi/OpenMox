import { create } from "zustand";
import type { Project, Agent, ChatMessage, Task, MemoryEntry } from "@/lib/types";

interface AppState {
  // Current project and window
  projects: Project[];
  currentProject: Project | null;
  currentWindowId: string | null;

  // Agents
  agents: Agent[];
  templates: { id: string; name: string; description: string; skills_count: number }[];

  // Chat
  messages: ChatMessage[];
  isStreaming: boolean;

  // Dashboard
  tasks: Task[];

  // Memory
  memories: MemoryEntry[];

  // Actions
  setProjects: (projects: Project[]) => void;
  setCurrentProject: (project: Project | null, windowId: string) => void;
  setAgents: (agents: Agent[]) => void;
  setTemplates: (templates: { id: string; name: string; description: string; skills_count: number }[]) => void;
  addMessage: (msg: ChatMessage) => void;
  appendToLastMessage: (agentId: string, delta: string) => void;
  setStreaming: (v: boolean) => void;
  setTasks: (tasks: Task[]) => void;
  setMemories: (memories: MemoryEntry[]) => void;
  backToProjects: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  projects: [],
  currentProject: null,
  currentWindowId: null,
  agents: [],
  templates: [],
  messages: [],
  isStreaming: false,
  tasks: [],
  memories: [],

  setProjects: (projects) => set({ projects }),
  setCurrentProject: (project, windowId) =>
    set({ currentProject: project, currentWindowId: windowId, messages: [], tasks: [], memories: [] }),
  setAgents: (agents) => set({ agents }),
  setTemplates: (templates) => set({ templates }),
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  appendToLastMessage: (agentId, delta) =>
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.sender === agentId) {
        msgs[msgs.length - 1] = { ...last, text: last.text + delta };
      }
      return { messages: msgs };
    }),
  setStreaming: (v) => set({ isStreaming: v }),
  setTasks: (tasks) => set({ tasks }),
  setMemories: (memories) => set({ memories }),
  backToProjects: () =>
    set({ currentProject: null, currentWindowId: null, messages: [], tasks: [], memories: [] }),
}));
