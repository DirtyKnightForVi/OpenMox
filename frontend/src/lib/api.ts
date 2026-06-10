const API_BASE = "http://localhost:8000/api";

import type { Agent, Project } from "./types";

async function fetchAPI<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    let detail = `API ${path}: ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

// ── Projects ───────────────────────────────────────────

export async function listProjects() {
  return fetchAPI<Project[]>("/projects");
}

export async function createProject(name: string, path: string, display_name?: string) {
  return fetchAPI<{ id: number; name: string; full_path: string; display_name?: string }>("/projects/create", {
    method: "POST",
    body: JSON.stringify({ name, path, display_name }),
  });
}

// ── Agents ─────────────────────────────────────────────

export async function listAgents(projectKey?: string) {
  const path = projectKey ? `/agents/${projectKey}` : "/agents";
  return fetchAPI<Agent[]>(path);
}

export async function listTemplates() {
  return fetchAPI<{ id: string; name: string; description: string; skills_count: number }[]>("/agent-templates");
}

export async function createAgent(projectKey: string, agentId: string, templateId: string, name?: string) {
  return fetchAPI<{ ok: boolean }>(`/agents/${projectKey}`, {
    method: "POST",
    body: JSON.stringify({ agent_id: agentId, template_id: templateId, name }),
  });
}

export async function deleteAgent(projectKey: string, agentId: string) {
  return fetchAPI<{ ok: boolean }>(`/agents/${projectKey}/${agentId}`, { method: "DELETE" });
}

// ── Dashboard ──────────────────────────────────────────

export async function getDashboard(windowId?: string, projectPath?: string) {
  const params = new URLSearchParams();
  if (windowId) params.set("window_id", windowId);
  if (projectPath) params.set("project_path", projectPath);
  return fetchAPI<{ phases: Record<string, any[]>; total: number }>(`/dashboard?${params}`);
}

export async function updateDashboardTask(taskId: string, updates: Record<string, any>, projectPath?: string) {
  const params = new URLSearchParams();
  if (projectPath) params.set("project_path", projectPath);
  return fetchAPI<{ ok: boolean }>(`/dashboard/${taskId}?${params}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

// ── Memory ─────────────────────────────────────────────

export async function listMemory(agentId: string, scope?: string, limit = 50) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (scope) params.set("scope", scope);
  return fetchAPI<{ entries: any[]; total: number }>(`/memory/${agentId}?${params}`);
}

export async function updateMemory(agentId: string, entryId: number, updates: Record<string, any>) {
  return fetchAPI<{ ok: boolean }>(`/memory/${agentId}/${entryId}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function triggerReflect(agentId: string, scope = "quick", windowId?: string) {
  const params = new URLSearchParams({ scope });
  if (windowId) params.set("window_id", windowId);
  return fetchAPI<{ ok: boolean }>(`/memory/${agentId}/reflect?${params}`, { method: "POST" });
}

export async function rollbackSnapshot(agentId: string, snapshotId: number) {
  return fetchAPI<{ ok: boolean }>(`/memory/${agentId}/rollback/${snapshotId}`, { method: "POST" });
}
