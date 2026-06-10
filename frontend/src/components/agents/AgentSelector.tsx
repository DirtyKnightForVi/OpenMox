"use client";

import { clsx } from "clsx";
import { getAgentColor } from "./AgentColorMap";
import type { Agent } from "@/lib/types";

interface AgentSelectorProps {
  agents: Agent[];
  value: string;
  onChange: (agentId: string) => void;
}

export function AgentSelector({ agents, value, onChange }: AgentSelectorProps) {
  return (
    <div className="flex items-center gap-1">
      {agents.map((a) => {
        const color = getAgentColor(a.id);
        const isActive = value === a.id;
        return (
          <button
            key={a.id}
            onClick={() => onChange(a.id)}
            className={clsx(
              "size-7 rounded-full text-[10px] font-semibold flex items-center justify-center transition-all",
              color.bg,
              color.text,
              isActive && "ring-2 ring-accent scale-110",
              !isActive && "opacity-60 hover:opacity-100",
            )}
            title={`@${a.id} — ${a.name || a.id}`}
            aria-label={`Select agent ${a.name || a.id}`}
          >
            {a.id[0].toUpperCase()}
          </button>
        );
      })}
    </div>
  );
}
