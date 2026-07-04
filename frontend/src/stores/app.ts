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
  TaskProgressEvent,
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

  // ── Task panel progress ──
  taskProgress: Record<string, TaskProgressEvent[]>;

  // ── Window / Topic tabs ──
  windowTabs: WindowTab[];
  activeWindowId: string;
  currentProjectPath: string;

  // Actions
  setProjects: (projects: Project[]) => void;
  setCurrentProject: (project: Project | null, windowId: string) => void;
  setCurrentProjectPath: (path: string) => void;
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
  addTaskProgress: (event: TaskProgressEvent) => void;
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
  taskProgress: {},
  windowTabs: [],
  activeWindowId: '',
  currentProjectPath: '',

  setProjects: (projects) => set({ projects }),
  setCurrentProject: (project, windowId) =>
    set({ currentProject: project, currentWindowId: windowId, messages: [], tasks: [], memories: [] }),
  setAgents: (agents) => set({ agents }),
  setTemplates: (templates) => set({ templates }),
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  appendToLastMessage: (agentId, delta) =>
    set((s) => {
      const msgs = [...s.messages];
      // Search backward for the last message belonging to this agent.
      // When 2+ agents reply concurrently, checking only msgs[last] would
      // route one agent's TEXT_BLOCK_DELTA to the wrong bubble.
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].sender === agentId) {
          msgs[i] = { ...msgs[i], text: msgs[i].text + delta };
          break;
        }
      }
      return { messages: msgs };
    }),
  appendThinkingToLastMessage: (agentId, delta) =>
    set((s) => {
      const msgs = [...s.messages];
      // Search backward for the last message belonging to this agent.
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].sender === agentId) {
          msgs[i] = { ...msgs[i], thinkingText: (msgs[i].thinkingText || "") + delta };
          break;
        }
      }
      return { messages: msgs };
    }),
  setStreaming: (v) => set({ isStreaming: v }),
  setTasks: (tasks) => set({ tasks }),
  setMemories: (memories) => set({ memories }),
  backToProjects: () =>
    set({ currentProject: null, currentWindowId: null, messages: [], tasks: [], memories: [],
      agentStatus: {}, agentWorkDetail: {}, windowTabs: [], taskProgress: {} }),

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
  addTaskProgress: (event) =>
    set((s) => {
      const key = event.worker_agent_id;
      const existing = s.taskProgress[key] || [];
      // Cap at 200 events per worker to avoid memory bloat
      const trimmed = existing.length >= 200 ? existing.slice(-150) : existing;
      return {
        taskProgress: { ...s.taskProgress, [key]: [...trimmed, event] },
      };
    }),
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
  setCurrentProjectPath: (path) => set({ currentProjectPath: path }),
}));
