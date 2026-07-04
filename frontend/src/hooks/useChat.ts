"use client";
import { useCallback, useRef } from "react";
import { toast } from "sonner";
import { queryRepo } from "@/lib/api";
import { useAppStore, useActiveSession } from "@/lib/store";
import { generateId, faithfulnessInfo } from "@/lib/utils";
import type { ChatMessage, Citation } from "@/types";

export function useChat() {
  const store = useAppStore();
  const activeSession = useActiveSession();
  const abortRef = useRef<(() => void) | null>(null);

  const sendMessage = useCallback(
    async (content: string) => {
      const { activeRepoKey, createSession, activeSessionId, addMessage, updateMessage } = store;

      if (!activeRepoKey) {
        toast.error("Select a repository first");
        return;
      }

      let sessionId = activeSessionId;
      if (!sessionId || store.sessions.find((s) => s.id === sessionId)?.repoKey !== activeRepoKey) {
        const session = createSession(activeRepoKey);
        sessionId = session.id;
      }

      // Add user message
      const userMsg: ChatMessage = {
        id: generateId(),
        role: "user",
        content,
        timestamp: new Date().toISOString(),
      };
      addMessage(sessionId, userMsg);

      // Add streaming assistant message placeholder
      const assistantMsgId = generateId();
      const assistantMsg: ChatMessage = {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        timestamp: new Date().toISOString(),
        isStreaming: true,
      };
      addMessage(sessionId, assistantMsg);

      try {
        // Use full query endpoint for structured response
        const response = await queryRepo(content, true);

        // Build citations
        const citations: Citation[] = response.sources.map((src, i) => ({
          id: i + 1,
          source: src,
        }));

        const faithfulness = faithfulnessInfo(
          response.faithfulness_score,
          response.is_faithful
        );

        updateMessage(sessionId, assistantMsgId, {
          content: response.answer,
          isStreaming: false,
          citations,
          faithfulness,
          sources: response.sources,
          activeRepo: response.active_repo ?? activeRepoKey,
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Query failed";
        updateMessage(sessionId, assistantMsgId, {
          content: `Error: ${msg}`,
          isStreaming: false,
        });
      }
    },
    [store]
  );

  const regenerate = useCallback(async () => {
    if (!activeSession) return;
    const messages = activeSession.messages;
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (lastUser) await sendMessage(lastUser.content);
  }, [activeSession, sendMessage]);

  return { sendMessage, regenerate, activeSession };
}
