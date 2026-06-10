"use client";

import { clsx } from "clsx";
import { getAgentColor, getAgentInitials } from "./AgentColorMap";

interface AgentAvatarProps {
  agentId: string;
  name?: string;
  size?: "sm" | "md" | "lg";
  isMomo?: boolean;
}

const sizeMap = {
  sm: "size-6 text-[10px]",
  md: "size-8 text-xs",
  lg: "size-10 text-sm",
};

export function AgentAvatar({ agentId, name, size = "md", isMomo }: AgentAvatarProps) {
  const color = getAgentColor(agentId);
  const initials = getAgentInitials(agentId, name);

  return (
    <span
      className={clsx(
        "inline-flex items-center justify-center rounded-full font-semibold shrink-0",
        sizeMap[size],
        color.bg,
        color.text,
        isMomo && "ring-2 ring-amber-400 dark:ring-amber-500",
      )}
      title={name || agentId}
    >
      {initials}
    </span>
  );
}
