"use client";
import { useRef, useEffect } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { EmptyState } from "@/components/chat/EmptyState";
import { UserMessage } from "@/components/chat/UserMessage";
import { AssistantMessage } from "@/components/chat/AssistantMessage";
import { Composer } from "@/components/chat/Composer";
import { useActiveSession, useAppStore } from "@/lib/store";
import { useChat } from "@/hooks/useChat";
import { cn } from "@/lib/utils";

export function ChatPane() {
  const { sendMessage, regenerate } = useChat();
  const activeSession = useActiveSession();
  const { activeRepoKey } = useAppStore();
  const bottomRef = useRef<HTMLDivElement>(null);
  const messages = activeSession?.messages ?? [];
  const isLoading = messages.some((m) => m.isStreaming);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, messages[messages.length - 1]?.content?.length]);

  const handleSend = (content: string) => {
    sendMessage(content);
  };

  return (
    <div className="flex flex-col flex-1 min-w-0 h-full">
      {/* Message area */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <EmptyState onPromptSelect={handleSend} />
        ) : (
          <div className="max-w-3xl mx-auto">
            {messages.map((msg, i) =>
              msg.role === "user" ? (
                <UserMessage key={msg.id} message={msg} />
              ) : (
                <AssistantMessage
                  key={msg.id}
                  message={msg}
                  onRegenerate={
                    i === messages.length - 1 && !isLoading ? regenerate : undefined
                  }
                />
              )
            )}
            <div ref={bottomRef} className="h-4" />
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="max-w-3xl w-full mx-auto px-0">
        <Composer onSend={handleSend} disabled={!activeRepoKey} isLoading={isLoading} />
      </div>
    </div>
  );
}
