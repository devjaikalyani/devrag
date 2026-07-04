"use client";
import { motion } from "framer-motion";
import { useAppStore } from "@/lib/store";
import { useActiveRepo } from "@/lib/store";
import { cn } from "@/lib/utils";

const SUGGESTED_PROMPTS = [
  {
    title: "High-level overview",
    prompt: "What does this project do? Give me a high-level overview of the architecture and main components.",
  },
  {
    title: "Authentication flow",
    prompt: "How does authentication work in this codebase? Walk me through the auth flow.",
  },
  {
    title: "API endpoints",
    prompt: "What API endpoints are available and what do they do? Include request/response shapes.",
  },
  {
    title: "Add a feature",
    prompt: "How would I add a new feature following the existing patterns in this codebase?",
  },
];

interface EmptyStateProps {
  onPromptSelect: (prompt: string) => void;
}

export function EmptyState({ onPromptSelect }: EmptyStateProps) {
  const { activeRepoKey } = useAppStore();
  const activeRepo = useActiveRepo();

  return (
    <div className="flex flex-col items-center justify-center h-full px-8 bg-grid">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="max-w-xl w-full text-center"
      >
        {/* Hero headline */}
        <h1
          className="text-[2.5rem] leading-tight text-white/90 mb-2"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Ask anything about your code.
        </h1>

        {activeRepo ? (
          <p className="text-sm text-white/40 mb-10 font-mono">
            Active:{" "}
            <span className="text-[var(--color-accent)]">{activeRepo.name}</span>
            {" "}· {activeRepo.chunkCount.toLocaleString()} chunks indexed
          </p>
        ) : (
          <p className="text-sm text-white/35 mb-10">
            Ingest a repository from the sidebar to get started.
          </p>
        )}

        {/* Suggested prompts */}
        {activeRepoKey && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.15, duration: 0.3 }}
            className="grid grid-cols-2 gap-2.5"
          >
            {SUGGESTED_PROMPTS.map((item, i) => (
              <motion.button
                key={item.title}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + i * 0.06 }}
                onClick={() => onPromptSelect(item.prompt)}
                className={cn(
                  "text-left p-3.5 rounded-md border border-[var(--color-border)]",
                  "bg-[var(--color-bg-subtle)] hover:bg-[var(--color-bg-elevated)]",
                  "hover:border-[var(--color-border-strong)] transition-colors",
                  "group"
                )}
              >
                <div className="text-xs font-medium text-white/70 group-hover:text-white mb-1 transition-colors">
                  {item.title}
                </div>
                <div className="text-[11px] text-white/35 leading-relaxed line-clamp-2">
                  {item.prompt}
                </div>
              </motion.button>
            ))}
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
