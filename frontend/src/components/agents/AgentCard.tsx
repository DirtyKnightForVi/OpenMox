"use client";

import { Trash, Star } from "@phosphor-icons/react";
import { AgentAvatar } from "./AgentAvatar";
import { Button } from "@/components/ui/Button";
import type { Agent } from "@/lib/types";

interface AgentCardProps {
  agent: Agent;
  onDelete?: (agentId: string) => void;
}

export function AgentCard({ agent, onDelete }: AgentCardProps) {
  return (
    <div className="bg-surface rounded-xl border border-border p-4 flex items-center gap-4">
      <AgentAvatar agentId={agent.id} name={agent.name} size="md" isMomo={agent.is_momo} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm text-text-primary">{agent.name || agent.id}</span>
          <span className="text-xs text-text-muted font-mono">({agent.id})</span>
          {agent.is_momo && <Star size={12} weight="fill" className="text-amber-500 shrink-0" />}
        </div>
        <div className="text-xs text-text-secondary mt-0.5 truncate">
          {agent.description || "No description"}
        </div>
      </div>
      {onDelete && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onDelete(agent.id)}
          className="text-text-muted hover:text-red-500"
          aria-label={`Delete ${agent.name || agent.id}`}
        >
          <Trash size={16} />
        </Button>
      )}
    </div>
  );
}
