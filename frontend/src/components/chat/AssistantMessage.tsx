"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { Copy, RefreshCw, ThumbsUp, ThumbsDown, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { FaithfulnessBadge } from "./FaithfulnessBadge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types";

interface AssistantMessageProps {
  message: ChatMessage;
  onRegenerate?: () => void;
}

export function AssistantMessage({ message, onRegenerate }: AssistantMessageProps) {
  const [actionsVisible, setActionsVisible] = useState(false);
  const [voted, setVoted] = useState<"up" | "down" | null>(null);

  const copyContent = () => {
    navigator.clipboard.writeText(message.content);
    toast.success("Copied to clipboard");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="group relative py-4 px-5 border-b border-[var(--color-border)]"
      onMouseEnter={() => setActionsVisible(true)}
      onMouseLeave={() => setActionsVisible(false)}
    >
      {/* Streaming indicator */}
      {message.isStreaming && (
        <div className="flex items-center gap-2 mb-3 text-[11px] text-white/35">
          <Loader2 size={10} className="animate-spin" />
          <span>Generating…</span>
        </div>
      )}

      {/* Content */}
      {message.isStreaming && !message.content ? (
        <div className="space-y-2">
          <div className="h-3 bg-white/[0.05] rounded animate-pulse w-3/4" />
          <div className="h-3 bg-white/[0.05] rounded animate-pulse w-full" />
          <div className="h-3 bg-white/[0.05] rounded animate-pulse w-5/6" />
        </div>
      ) : (
        <MarkdownRenderer
          content={message.content}
          citations={message.citations}
          isStreaming={message.isStreaming}
        />
      )}

      {/* Faithfulness badge */}
      {!message.isStreaming && message.faithfulness && (
        <FaithfulnessBadge info={message.faithfulness} />
      )}

      {/* Action row */}
      {!message.isStreaming && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: actionsVisible ? 1 : 0 }}
          transition={{ duration: 0.12 }}
          className="flex items-center gap-0.5 mt-3"
        >
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={copyContent}
            title="Copy"
          >
            <Copy size={11} />
          </Button>
          {onRegenerate && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onRegenerate}
              title="Regenerate"
            >
              <RefreshCw size={11} />
            </Button>
          )}
          <div className="w-px h-3 bg-white/10 mx-1" />
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setVoted(voted === "up" ? null : "up")}
            className={cn(voted === "up" && "text-green-400")}
            title="Helpful"
          >
            <ThumbsUp size={11} />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setVoted(voted === "down" ? null : "down")}
            className={cn(voted === "down" && "text-red-400")}
            title="Not helpful"
          >
            <ThumbsDown size={11} />
          </Button>

          {message.citations?.length ? (
            <>
              <div className="w-px h-3 bg-white/10 mx-1" />
              <span className="text-[10px] text-white/25 font-mono">
                {message.citations.length} source{message.citations.length !== 1 ? "s" : ""}
              </span>
            </>
          ) : null}
        </motion.div>
      )}
    </motion.div>
  );
}
