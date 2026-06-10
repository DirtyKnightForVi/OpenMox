"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { clsx } from "clsx";
import { CaretDown, Brain } from "@phosphor-icons/react";
import { AgentAvatar } from "@/components/agents/AgentAvatar";
import type { ChatMessage } from "@/lib/types";

interface ChatBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

export function ChatBubble({ message, isStreaming }: ChatBubbleProps) {
  const isUser = message.sender === "user";
  const isSystem = message.sender === "system";
  const hasThinking = !!message.thinkingText;
  const [thinkingOpen, setThinkingOpen] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className={clsx("flex", isUser ? "justify-end" : "justify-start")}
    >
      {isUser ? (
        <div className="max-w-[70%] rounded-2xl px-4 py-2.5 bg-bubble-user text-white text-sm leading-relaxed">
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
            message.sender === "momo" && "border-l-4 border-l-blue-400",
            message.sender === "product-manager" && "border-l-4 border-l-amber-400",
            message.sender === "dev-manager" && "border-l-4 border-l-indigo-400",
            message.sender === "arch-manager" && "border-l-4 border-l-rose-400",
          )}
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

          {/* Main text */}
          <div className="text-text-primary whitespace-pre-wrap break-words">
            {message.text || (
              <span className="text-text-muted italic">thinking...</span>
            )}
          </div>
        </div>
      )}
    </motion.div>
  );
}
