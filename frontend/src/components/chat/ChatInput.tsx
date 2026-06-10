"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { At, PaperPlaneTilt } from "@phosphor-icons/react";
import { clsx } from "clsx";
import { getAgentColor } from "@/components/agents/AgentColorMap";
import type { Agent } from "@/lib/types";

interface ChatInputProps {
  agents: Agent[];
  isStreaming: boolean;
  onSend: (text: string) => void;
}

export function ChatInput({ agents, isStreaming, onSend }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [showMention, setShowMention] = useState(false);
  const [mentionQuery, setMentionQuery] = useState("");
  const [mentionIndex, setMentionIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const mentionRef = useRef<HTMLDivElement>(null);

  const filteredAgents = mentionQuery
    ? agents.filter(
        (a) =>
          a.id.toLowerCase().includes(mentionQuery.toLowerCase()) ||
          (a.name && a.name.toLowerCase().includes(mentionQuery.toLowerCase())),
      )
    : agents;

  // Track @ mentions: find the position of @ sign after the last space / start
  const handleInput = useCallback(
    (value: string) => {
      setInput(value);
      const lastAtIndex = value.lastIndexOf("@");
      if (lastAtIndex >= 0) {
        // Check if there's a space before @ (or @ is at start) — active mention
        const beforeAt = lastAtIndex === 0 ? " " : value[lastAtIndex - 1];
        if (beforeAt === " " || beforeAt === "\n") {
          const query = value.slice(lastAtIndex + 1);
          // Only show if the query doesn't contain a space (still typing the mention)
          if (!query.includes(" ")) {
            setMentionQuery(query);
            setShowMention(true);
            setMentionIndex(0);
            return;
          }
        }
      }
      setShowMention(false);
    },
    [],
  );

  const insertMention = useCallback(
    (agentId: string) => {
      const lastAtIndex = input.lastIndexOf("@");
      const before = input.slice(0, lastAtIndex);
      const after = input.slice(lastAtIndex + mentionQuery.length + 1);
      const newValue = `${before}@${agentId} ${after}`;
      setInput(newValue);
      setShowMention(false);
      inputRef.current?.focus();
    },
    [input, mentionQuery.length],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (showMention && filteredAgents.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setMentionIndex((prev) => (prev + 1) % filteredAgents.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setMentionIndex((prev) => (prev - 1 + filteredAgents.length) % filteredAgents.length);
        return;
      }
      if (e.key === "Tab" || e.key === "Enter") {
        if (e.key === "Enter" && !e.shiftKey && showMention) {
          e.preventDefault();
          insertMention(filteredAgents[mentionIndex].id);
          return;
        }
        if (e.key === "Tab") {
          e.preventDefault();
          insertMention(filteredAgents[mentionIndex].id);
          return;
        }
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !isStreaming) {
        onSend(input.trim());
        setInput("");
      }
    }
  };

  // Close mention dropdown on scroll outside
  useEffect(() => {
    const handler = () => setShowMention(false);
    document.addEventListener("scroll", handler, true);
    return () => document.removeEventListener("scroll", handler, true);
  }, []);

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    onSend(input.trim());
    setInput("");
  };

  return (
    <div className="border-t border-border p-3 bg-surface relative">
      {/* @mention dropdown */}
      {showMention && filteredAgents.length > 0 && (
        <div
          ref={mentionRef}
          className="absolute bottom-full left-3 right-3 mb-1 bg-surface rounded-xl border border-border shadow-lg overflow-hidden z-10"
        >
          {filteredAgents.map((a, i) => {
            const color = getAgentColor(a.id);
            return (
              <button
                key={a.id}
                onClick={() => insertMention(a.id)}
                onMouseEnter={() => setMentionIndex(i)}
                className={clsx(
                  "w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left transition-colors",
                  i === mentionIndex ? "bg-accent-soft" : "hover:bg-surface-tertiary",
                )}
              >
                <span
                  className={clsx(
                    "size-6 rounded-full text-[10px] font-semibold flex items-center justify-center shrink-0",
                    color.bg,
                    color.text,
                  )}
                >
                  {a.id[0].toUpperCase()}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="font-medium text-text-primary">{a.name || a.id}</span>
                  <span className="text-text-muted ml-1.5 text-xs font-mono">@{a.id}</span>
                </div>
                {a.is_momo && <span className="text-[10px] text-amber-500 font-medium">momo</span>}
              </button>
            );
          })}
        </div>
      )}

      <div className="flex items-center gap-2 bg-surface-tertiary rounded-xl px-4 py-2.5 border border-border/50 focus-within:border-accent/50 transition-colors">
        <button
          onClick={() => {
            setInput((prev) => prev + "@");
            inputRef.current?.focus();
          }}
          className="text-text-muted hover:text-text-secondary transition-colors shrink-0"
          title="Mention agent (@)"
          tabIndex={-1}
        >
          <At size={18} />
        </button>
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => handleInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message... @momo to start"
          className="flex-1 bg-transparent text-sm outline-none placeholder:text-text-muted text-text-primary"
          disabled={isStreaming}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || isStreaming}
          className={clsx(
            "p-1.5 rounded-lg transition-all shrink-0",
            input.trim() && !isStreaming
              ? "bg-accent text-white hover:bg-accent-hover"
              : "bg-surface-tertiary text-text-muted",
          )}
          aria-label="Send message"
        >
          <PaperPlaneTilt size={16} weight={input.trim() && !isStreaming ? "fill" : "regular"} />
        </button>
      </div>
    </div>
  );
}
