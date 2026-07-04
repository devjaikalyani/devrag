"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, AlertTriangle, XCircle, ChevronDown } from "lucide-react";
import {
  Tooltip, TooltipTrigger, TooltipContent, TooltipProvider,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { FaithfulnessInfo } from "@/types";

interface FaithfulnessBadgeProps {
  info: FaithfulnessInfo;
}

const CONFIG = {
  verified: {
    icon: CheckCircle2,
    color: "text-green-400",
    bg: "bg-green-500/[0.08] border-green-500/20",
    label: "Verified",
  },
  partial: {
    icon: AlertTriangle,
    color: "text-amber-400",
    bg: "bg-amber-500/[0.08] border-amber-500/20",
    label: "Partially supported",
  },
  low: {
    icon: XCircle,
    color: "text-red-400",
    bg: "bg-red-500/[0.08] border-red-500/20",
    label: "Low confidence",
  },
};

export function FaithfulnessBadge({ info }: FaithfulnessBadgeProps) {
  const [expanded, setExpanded] = useState(false);
  const cfg = CONFIG[info.level];
  const Icon = cfg.icon;
  const score = Math.round(info.score * 100);

  return (
    <TooltipProvider>
      <div className="mt-2 inline-flex flex-col">
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={() => setExpanded(!expanded)}
              className={cn(
                "inline-flex items-center gap-1.5 px-2 py-1 rounded border text-[11px] font-medium transition-colors",
                cfg.bg, cfg.color
              )}
            >
              <Icon size={11} />
              {cfg.label}
              <span className="ml-1 font-mono opacity-70">{score}%</span>
              {info.flagged_sentences?.length ? (
                <ChevronDown
                  size={10}
                  className={cn("ml-0.5 transition-transform", expanded && "rotate-180")}
                />
              ) : null}
            </button>
          </TooltipTrigger>
          <TooltipContent>
            NLI faithfulness score: {score}% — measures how well the answer is supported by retrieved sources.
          </TooltipContent>
        </Tooltip>

        <AnimatePresence>
          {expanded && info.flagged_sentences?.length ? (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.18 }}
              className="overflow-hidden"
            >
              <div className="mt-1.5 rounded-md border border-[var(--color-border)] bg-[var(--color-bg-overlay)] p-2.5 space-y-1">
                <p className="text-[10px] text-white/40 font-medium uppercase tracking-wider">
                  Flagged sentences
                </p>
                {info.flagged_sentences.map((s, i) => (
                  <p key={i} className="text-[11px] text-amber-300/80 leading-relaxed">
                    "{s}"
                  </p>
                ))}
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
    </TooltipProvider>
  );
}
