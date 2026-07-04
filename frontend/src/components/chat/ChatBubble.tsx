"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { clsx } from "clsx";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CaretDown, Brain } from "@phosphor-icons/react";
import { AgentAvatar } from "@/components/agents/AgentAvatar";
import { getAgentColor } from "@/components/agents/AgentColorMap";
import type { ChatMessage } from "@/lib/types";

/** Map from getAgentColor dot class → inline border color hex */
const AGENT_BORDER_COLORS: Record<string, string> = {
  "bg-blue-500": "#3b82f6",
  "bg-amber-500": "#f59e0b",
  "bg-indigo-500": "#6366f1",
  "bg-rose-500": "#f43f5e",
  "bg-emerald-500": "#10b981",
  "bg-purple-500": "#a855f7",
  "bg-cyan-500": "#06b6d4",
  "bg-orange-500": "#f97316",
};

interface ChatBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

export function ChatBubble({ message, isStreaming }: ChatBubbleProps) {
  const isUser = message.sender === "user";
  const isSystem = message.sender === "system";
  const hasThinking = !!message.thinkingText;
  const [thinkingOpen, setThinkingOpen] = useState(false);
  const agentColor = isUser || isSystem ? null : getAgentColor(message.sender);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className={clsx("flex", isUser ? "justify-end" : "justify-start")}
    >
      {isUser ? (
        <div className="max-w-[70%] rounded-2xl px-4 py-2.5 bg-bubble-user text-white text-sm leading-relaxed whitespace-pre-wrap break-words">
          {message.text}
        </div>
      ) : isSystem ? (
        <div className="max-w-[80%] text-xs text-text-muted italic text-center mx-auto">
          {message.text}
        </div>
      ) : (
        <div
          className={clsx(
            "max-w-[75%] rounded-xl px-4 py-2.5 text-sm leading-relaxed border border-border/50 bubble-agent",
          )}
          style={
            agentColor
              ? { borderLeft: `4px solid ${AGENT_BORDER_COLORS[agentColor.dot] || "#94a3b8"}` }
              : undefined
          }
        >
          {/* Agent header */}
          <div className="flex items-center gap-2 mb-1.5">
            <AgentAvatar agentId={message.sender} size="sm" />
            <span className="text-xs font-medium text-text-secondary">{message.sender}</span>
            {isStreaming && (
              <span className="flex gap-[2px] ml-1">
                <span className="size-1 rounded-full bg-text-muted animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="size-1 rounded-full bg-text-muted animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="size-1 rounded-full bg-text-muted animate-bounce" style={{ animationDelay: "300ms" }} />
              </span>
            )}
          </div>

          {/* Thinking / Reasoning block (collapsible) */}
          {hasThinking && (
            <div className="mb-2">
              <button
                onClick={() => setThinkingOpen(!thinkingOpen)}
                className="flex items-center gap-1.5 text-[11px] text-text-muted hover:text-text-secondary transition-colors w-full"
              >
                <Brain size={12} weight="fill" />
                <span>Reasoning</span>
                <CaretDown
                  size={12}
                  className={clsx(
                    "transition-transform",
                    thinkingOpen ? "rotate-0" : "-rotate-90",
                  )}
                />
              </button>
              {thinkingOpen && (
                <div className="mt-1.5 text-xs text-text-muted bg-surface-tertiary/50 rounded-lg p-3 leading-relaxed whitespace-pre-wrap border border-border/30">
                  {message.thinkingText}
                </div>
              )}
            </div>
          )}

          {/* Main text — rendered as Markdown */}
          <div className="text-text-primary break-words prose prose-sm dark:prose-invert max-w-none">
            {message.text ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.text}
              </ReactMarkdown>
            ) : (
              <span className="text-text-muted italic">thinking...</span>
            )}
          </div>
        </div>
      )}
    </motion.div>
  );
}
