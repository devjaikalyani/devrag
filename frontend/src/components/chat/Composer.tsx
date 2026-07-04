"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { motion } from "framer-motion";
import { Send, ChevronDown, Sliders, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from "@/components/ui/tooltip";
import { useAppStore, useActiveRepo } from "@/lib/store";
import { cn } from "@/lib/utils";

const SLASH_COMMANDS = [
  { cmd: "/explain", desc: "Explain a function or module" },
  { cmd: "/find", desc: "Find where something is defined" },
  { cmd: "/diagram", desc: "Describe architecture as a diagram" },
];

interface ComposerProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  isLoading?: boolean;
}

export function Composer({ onSend, disabled, isLoading }: ComposerProps) {
  const [value, setValue] = useState("");
  const [showCommands, setShowCommands] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { activeRepoKey } = useAppStore();
  const activeRepo = useActiveRepo();

  const tokenCount = Math.ceil(value.length / 4);

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setValue(val);
    autoResize();
    setShowCommands(val.startsWith("/") && val.length > 0 && !val.includes(" "));
  };

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled || isLoading || !activeRepoKey) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    setShowCommands(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSend();
    }
    if (e.key === "Escape") setShowCommands(false);
  };

  const selectCommand = (cmd: string) => {
    setValue(cmd + " ");
    setShowCommands(false);
    textareaRef.current?.focus();
  };

  return (
    <TooltipProvider>
      <div className="border-t border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-3">
        {/* Slash command suggestions */}
        {showCommands && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-2 rounded-md border border-[var(--color-border-strong)] bg-[var(--color-bg-overlay)] overflow-hidden"
          >
            {SLASH_COMMANDS.filter((c) =>
              c.cmd.startsWith(value.split(" ")[0])
            ).map((c) => (
              <button
                type="button"
                key={c.cmd}
                onClick={() => selectCommand(c.cmd)}
                className="flex items-center gap-3 w-full px-3 py-2 text-left hover:bg-white/[0.04] transition-colors"
              >
                <span className="font-mono text-xs text-[var(--color-accent)]">{c.cmd}</span>
                <span className="text-xs text-white/40">{c.desc}</span>
              </button>
            ))}
          </motion.div>
        )}

        {/* Main composer box */}
        <div
          className={cn(
            "rounded-md border transition-colors",
            "bg-[var(--color-bg)]",
            value.length > 0
              ? "border-[var(--color-border-strong)]"
              : "border-[var(--color-border)]",
            "focus-within:border-[var(--color-accent)]/40"
          )}
        >
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={
              activeRepoKey
                ? "Ask about the codebase… (⌘↵ to send)"
                : "Select a repository to start asking questions"
            }
            disabled={disabled || !activeRepoKey}
            rows={1}
            className={cn(
              "w-full resize-none bg-transparent px-3 pt-3 pb-2",
              "text-sm text-white placeholder:text-white/25",
              "focus:outline-none",
              "disabled:opacity-40 disabled:cursor-not-allowed",
              "min-h-[42px] max-h-[200px]",
              "leading-relaxed"
            )}
          />

          {/* Toolbar */}
          <div className="flex items-center justify-between px-2 pb-2">
            <div className="flex items-center gap-1">
              {/* Hybrid retrieval chip */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <button type="button" className="flex items-center gap-1 px-2 py-1 rounded text-[10px] text-white/35 hover:text-white/60 hover:bg-white/4 transition-colors font-mono">
                    <Zap size={9} />
                    Dense + BM25 + Rerank
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  Hybrid retrieval: Dense vector search + BM25 keyword matching, merged with RRF, then cross-encoder reranked.
                </TooltipContent>
              </Tooltip>
            </div>

            <div className="flex items-center gap-1.5">
              {/* Token counter */}
              {value.length > 0 && (
                <span className="text-[10px] text-white/25 font-mono">
                  ~{tokenCount}t
                </span>
              )}

              {/* Model chip */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <button type="button" className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] text-white/30 hover:text-white/60 hover:bg-white/4 transition-colors font-mono">
                    Llama 3.3 70B
                    <ChevronDown size={9} />
                  </button>
                </TooltipTrigger>
                <TooltipContent>Model selection (Groq Llama 3.3 70B)</TooltipContent>
              </Tooltip>

              {/* Send button */}
              <Button
                size="icon"
                onClick={handleSend}
                disabled={!value.trim() || disabled || isLoading || !activeRepoKey}
                className="h-7 w-7"
              >
                <Send size={12} />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}
