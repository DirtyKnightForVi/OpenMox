export interface Project {
  id: number;
  name: string;
  full_path: string;
  display_name?: string;
  created_at?: string;
}

export interface Agent {
  id: string;
  name: string;
  avatar: string;
  description: string;
  template?: string;
  is_momo: boolean;
}

export interface AgentTemplate {
  id: string;
  name: string;
  avatar: string;
  description: string;
  skills_count: number;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  phase: "research" | "development" | "review" | "delivery";
  owner: string;
  status: "pending" | "in_progress" | "done" | "blocked";
  depends_on: string[];
  window_id: string | null;
  output: string;
  blocked_reason: string;
  created_at: string;
  completed_at: string;
  communication_budget?: number;
}

export interface DashboardResponse {
  phases: Record<string, Task[]>;
  total: number;
}

export interface MemoryEntry {
  id: number;
  agent_id: string;
  scope: "private" | "shared";
  type: "fact" | "decision" | "preference" | "context" | "reflection" | "shendu";
  content: string;
  importance: number;
  pinned: number;
  deprecated: number;
  source: string;
  created_at: string;
}

export interface MemoryListResponse {
  entries: MemoryEntry[];
  total: number;
}

export interface MessageRecord {
  id: number;
  speaker_type: "human" | "agent";
  speaker_id: string;
  content: string;
  timestamp: number;
}

export interface ChatMessage {
  id: string;
  sender: "user" | string;
  text: string;
  thinkingText?: string;
  timestamp: number;
  events: ChatStreamEvent[];
}

export interface ChatStreamEvent {
  type: string;
  _agent_id: string;
  delta?: string;
  name?: string;
  _source?: string;
  _hint?: string;
  _timestamp: number;
}

// ── Agent status tracking ──

export type AgentConnectionStatus = 'idle' | 'busy';

export interface ToolCallEvent {
  name: string;
  _source?: string;
  _timestamp: number;
  state?: string;
}

export interface WorkDetail {
  toolCalls: ToolCallEvent[];
  thinkingBlocks: { delta: string; _timestamp: number }[];
  currentTask?: string;
}

// ── Window / Topic management ──

export interface WindowTab {
  id: string;
  label: string;
  projectName: string;
}
