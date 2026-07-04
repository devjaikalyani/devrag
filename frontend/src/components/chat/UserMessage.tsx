"use client";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types";

interface UserMessageProps {
  message: ChatMessage;
}

export function UserMessage({ message }: UserMessageProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      className="flex justify-end py-3 px-5"
    >
      <div
        className={cn(
          "max-w-[72%] px-3.5 py-2.5 rounded-md",
          "bg-white/[0.05] border border-white/[0.07]",
          "text-sm text-white/90 leading-relaxed"
        )}
      >
        {message.content}
      </div>
    </motion.div>
  );
}
