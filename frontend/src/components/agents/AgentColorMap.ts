/**
 * Deterministic color palette for agents based on their ID.
 * Each agent gets a consistent color scheme across the entire UI.
 */
export const AGENT_COLORS: Record<string, { bg: string; text: string; dot: string; label: string }> = {
  momo: {
    bg: "bg-blue-100 dark:bg-blue-900/30",
    text: "text-blue-700 dark:text-blue-300",
    dot: "bg-blue-500",
    label: "momo",
  },
  "product-manager": {
    bg: "bg-amber-100 dark:bg-amber-900/30",
    text: "text-amber-700 dark:text-amber-300",
    dot: "bg-amber-500",
    label: "PM",
  },
  "dev-manager": {
    bg: "bg-indigo-100 dark:bg-indigo-900/30",
    text: "text-indigo-700 dark:text-indigo-300",
    dot: "bg-indigo-500",
    label: "DEV",
  },
  "arch-manager": {
    bg: "bg-rose-100 dark:bg-rose-900/30",
    text: "text-rose-700 dark:text-rose-300",
    dot: "bg-rose-500",
    label: "ARCH",
  },
};

/** Fallback colors for unknown agents */
const FALLBACK_PALETTE = [
  { bg: "bg-emerald-100 dark:bg-emerald-900/30", text: "text-emerald-700 dark:text-emerald-300", dot: "bg-emerald-500", label: "?" },
  { bg: "bg-purple-100 dark:bg-purple-900/30", text: "text-purple-700 dark:text-purple-300", dot: "bg-purple-500", label: "?" },
  { bg: "bg-cyan-100 dark:bg-cyan-900/30", text: "text-cyan-700 dark:text-cyan-300", dot: "bg-cyan-500", label: "?" },
  { bg: "bg-orange-100 dark:bg-orange-900/30", text: "text-orange-700 dark:text-orange-300", dot: "bg-orange-500", label: "?" },
];

/** Get color scheme for any agent ID (deterministic) */
export function getAgentColor(agentId: string) {
  if (AGENT_COLORS[agentId]) return AGENT_COLORS[agentId];
  let hash = 0;
  for (let i = 0; i < agentId.length; i++) hash = agentId.charCodeAt(i) + ((hash << 5) - hash);
  return FALLBACK_PALETTE[Math.abs(hash) % FALLBACK_PALETTE.length];
}

/** Get initial letter(s) for an agent */
export function getAgentInitials(agentId: string, name?: string): string {
  if (name) {
    const parts = name.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.slice(0, 2).toUpperCase();
  }
  if (AGENT_COLORS[agentId]) return AGENT_COLORS[agentId].label;
  // For composite IDs like "pd-2", take first segment
  const segment = agentId.split("-")[0];
  return segment.slice(0, 2).toUpperCase();
}
