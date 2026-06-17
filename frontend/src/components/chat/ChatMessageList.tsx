"use client";

import { useRef, useEffect, useCallback } from "react";
import { clsx } from "clsx";
import { ChatBubble } from "./ChatBubble";
import { ChatMessageSkeleton } from "@/components/ui/Skeleton";
import type { ChatMessage } from "@/lib/types";

interface ChatMessageListProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  isLoading?: boolean;
  wsConnected?: boolean;
}

export function ChatMessageList({ messages, isStreaming, isLoading, wsConnected }: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  if (isLoading) {
    return (
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
        <ChatMessageSkeleton />
        <ChatMessageSkeleton />
      </div>
    );
  }

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full text-text-muted text-sm px-6">
          {/* Chat icon */}
          <div className="size-14 rounded-2xl bg-surface-tertiary flex items-center justify-center mb-4">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-text-muted">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
            </svg>
          </div>

          <p className={clsx("font-medium", isStreaming && "animate-pulse")}>
            {isStreaming ? "Agents are thinking..." : "Start a conversation"}
          </p>
          <p className="text-xs mt-1.5 text-center max-w-xs">
            Type a message or @mention an agent to begin collaborating
          </p>

          {/* Tips */}
          <div className="mt-6 space-y-2 text-xs">
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-tertiary/50">
              <code className="text-accent font-mono text-[11px]">@momo</code>
              <span className="text-text-muted">Assign tasks to the coordinator</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-tertiary/50">
              <code className="text-accent font-mono text-[11px]">@product-manager</code>
              <span className="text-text-muted">Ask for analysis</span>
            </div>
          </div>

          {/* Connection hint */}
          {wsConnected === false && (
            <div className="mt-6 flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 text-xs">
              <span className="size-1.5 rounded-full bg-amber-400 animate-pulse" />
              Connecting to server...
            </div>
          )}
        </div>
      )}

      {messages.map((msg, idx) => (
        <ChatBubble
          key={msg.id}
          message={msg}
          isStreaming={isStreaming && idx === messages.length - 1 && msg.sender !== "user"}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
