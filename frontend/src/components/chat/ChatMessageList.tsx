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
}

export function ChatMessageList({ messages, isStreaming, isLoading }: ChatMessageListProps) {
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
    <div ref={containerRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full text-text-muted text-sm">
          <div className="size-12 rounded-full bg-surface-tertiary flex items-center justify-center mb-3">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-text-muted">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
            </svg>
          </div>
          <p className={clsx("font-medium", isStreaming && "animate-pulse")}>
            {isStreaming ? "Agents are thinking..." : "Send a message to start collaborating"}
          </p>
          <p className="text-xs mt-1">Use @AgentName to address specific agents</p>
        </div>
      )}

      {messages.map((msg) => (
        <ChatBubble
          key={msg.id}
          message={msg}
          isStreaming={isStreaming && msg === messages[messages.length - 1] && msg.sender !== "user"}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
