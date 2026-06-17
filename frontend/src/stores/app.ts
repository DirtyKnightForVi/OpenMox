import { create } from "zustand";
import type {
  Project,
  Agent,
  ChatMessage,
  Task,
  MemoryEntry,
  AgentConnectionStatus,
  WorkDetail,
  ToolCallEvent,
  WindowTab,
} from "@/lib/types";

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

  // ── Agent status tracking ──
  agentStatus: Record<string, AgentConnectionStatus>;
  agentWorkDetail: Record<string, WorkDetail>;
  wsConnected: boolean;

  // ── Window / Topic tabs ──
  windowTabs: WindowTab[];
  activeWindowId: string;

  // Actions
  setProjects: (projects: Project[]) => void;
  setCurrentProject: (project: Project | null, windowId: string) => void;
  setAgents: (agents: Agent[]) => void;
  setTemplates: (templates: { id: string; name: string; description: string; skills_count: number }[]) => void;
  addMessage: (msg: ChatMessage) => void;
  appendToLastMessage: (agentId: string, delta: string) => void;
  appendThinkingToLastMessage: (agentId: string, delta: string) => void;
  setStreaming: (v: boolean) => void;
  setTasks: (tasks: Task[]) => void;
  setMemories: (memories: MemoryEntry[]) => void;
  backToProjects: () => void;

  // ── Agent status actions ──
  setAgentStatus: (agentId: string, status: AgentConnectionStatus) => void;
  updateWorkDetail: (agentId: string, update: Partial<WorkDetail>) => void;
  addToolCallToAgent: (agentId: string, event: ToolCallEvent) => void;
  addThinkingToAgent: (agentId: string, delta: string) => void;
  setWsConnected: (v: boolean) => void;

  // ── Window / Topic actions ──
  addWindowTab: (tab: WindowTab) => void;
  removeWindowTab: (id: string) => void;
  setActiveWindowId: (id: string) => void;
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
  agentStatus: {},
  agentWorkDetail: {},
  wsConnected: false,
  windowTabs: [],
  activeWindowId: '',

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
  appendThinkingToLastMessage: (agentId, delta) =>
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.sender === agentId) {
        msgs[msgs.length - 1] = { ...last, thinkingText: (last.thinkingText || "") + delta };
      }
      return { messages: msgs };
    }),
  setStreaming: (v) => set({ isStreaming: v }),
  setTasks: (tasks) => set({ tasks }),
  setMemories: (memories) => set({ memories }),
  backToProjects: () =>
    set({ currentProject: null, currentWindowId: null, messages: [], tasks: [], memories: [],
      agentStatus: {}, agentWorkDetail: {}, windowTabs: [] }),

  // ── Agent status actions ──
  setAgentStatus: (agentId, status) =>
    set((s) => ({ agentStatus: { ...s.agentStatus, [agentId]: status } })),
  updateWorkDetail: (agentId, update) =>
    set((s) => ({
      agentWorkDetail: {
        ...s.agentWorkDetail,
        [agentId]: { ...(s.agentWorkDetail[agentId] || { toolCalls: [], thinkingBlocks: [] }), ...update },
      },
    })),
  addToolCallToAgent: (agentId, event) =>
    set((s) => ({
      agentWorkDetail: {
        ...s.agentWorkDetail,
        [agentId]: {
          ...(s.agentWorkDetail[agentId] || { toolCalls: [], thinkingBlocks: [] }),
          toolCalls: [...(s.agentWorkDetail[agentId]?.toolCalls || []), event],
        },
      },
    })),
  addThinkingToAgent: (agentId, delta) =>
    set((s) => ({
      agentWorkDetail: {
        ...s.agentWorkDetail,
        [agentId]: {
          ...(s.agentWorkDetail[agentId] || { toolCalls: [], thinkingBlocks: [] }),
          thinkingBlocks: [
            ...(s.agentWorkDetail[agentId]?.thinkingBlocks || []),
            { delta, _timestamp: Date.now() },
          ],
        },
      },
    })),
  setWsConnected: (v) => set({ wsConnected: v }),

  // ── Window / Topic actions ──
  addWindowTab: (tab) =>
    set((s) => {
      if (s.windowTabs.find((t) => t.id === tab.id)) return s;
      return { windowTabs: [...s.windowTabs, tab] };
    }),
  removeWindowTab: (id) =>
    set((s) => ({
      windowTabs: s.windowTabs.filter((t) => t.id !== id),
      activeWindowId: s.activeWindowId === id
        ? (s.windowTabs.find((t) => t.id !== id)?.id || '')
        : s.activeWindowId,
    })),
  setActiveWindowId: (id) => set({ activeWindowId: id }),
}));
