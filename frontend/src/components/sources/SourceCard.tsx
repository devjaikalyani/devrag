"use client";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, FileCode, ExternalLink } from "lucide-react";
import { codeToHtml } from "shiki";
import { cn, parseBreadcrumb, truncatePath, fileLanguage } from "@/lib/utils";
import type { Source } from "@/types";

// Cross-encoder reranker returns raw logits (can be very negative).
// Sigmoid maps any real number into (0, 1) for display.
function sigmoid(x: number): number {
  return 1 / (1 + Math.exp(-x));
}

const LANG_ICONS: Record<string, string> = {
  typescript: "TS", tsx: "TSX", javascript: "JS", jsx: "JSX",
  python: "PY", rust: "RS", go: "GO", java: "JV",
  cpp: "C++", c: "C", csharp: "C#", ruby: "RB",
  html: "HT", css: "CS", json: "JS", yaml: "YL",
  markdown: "MD", bash: "SH", plaintext: "TXT",
};

// value is already a 0–1 normalized score
function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.max(0, Math.min(value * 100, 100));
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[9px] text-white/25 w-12 shrink-0">{label}</span>
      <div className="flex-1 h-1 rounded-full bg-white/[0.06] overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className={cn("h-full rounded-full", color)}
        />
      </div>
      <span className="text-[9px] font-mono text-white/30 w-8 text-right">
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

interface SourceCardProps {
  source: Source;
  index: number;
  isActive: boolean;
  onClick: () => void;
}

export function SourceCard({ source, index, isActive, onClick }: SourceCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [html, setHtml] = useState<string>("");
  const { dir, file } = parseBreadcrumb(source.source);
  const lang = source.language ?? fileLanguage(source.source);
  const langIcon = LANG_ICONS[lang] ?? "{}";

  useEffect(() => {
    if (expanded && source.text_preview && !html) {
      codeToHtml(source.text_preview, {
        lang,
        theme: "github-dark-dimmed",
      })
        .then(setHtml)
        .catch(() => setHtml(`<pre><code>${source.text_preview}</code></pre>`));
    }
  }, [expanded, source.text_preview, lang]);

  return (
    <motion.div
      layout
      id={`source-${index + 1}`}
      className={cn(
        "border-b border-[var(--color-border)] transition-colors",
        isActive && "cite-highlighted bg-[var(--color-accent-dim)]"
      )}
    >
      <div
        className="p-3 cursor-pointer hover:bg-white/[0.02] transition-colors"
        onClick={() => { onClick(); setExpanded(!expanded); }}
      >
        {/* Header row */}
        <div className="flex items-start gap-2">
          {/* Citation number */}
          <span className="flex-none mt-0.5 h-4 w-4 rounded bg-[var(--color-accent-dim)] text-[var(--color-accent)] text-[9px] font-bold font-mono flex items-center justify-center">
            {index + 1}
          </span>

          <div className="flex-1 min-w-0">
            {/* File path breadcrumb */}
            <div className="flex items-center gap-1 flex-wrap">
              {dir && (
                <span className="text-[10px] font-mono text-white/30 truncate max-w-[140px]">
                  {truncatePath(dir, 28)}
                </span>
              )}
              {dir && <span className="text-white/20 text-[10px]">/</span>}
              <span className="text-[10px] font-mono text-white/80 font-medium">{file}</span>
              {(source.start_line || source.end_line) && (
                <span className="text-[9px] font-mono text-white/25">
                  :{source.start_line}–{source.end_line}
                </span>
              )}
            </div>

            {/* Lang + scores row */}
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[9px] font-mono bg-white/[0.05] px-1 py-0.5 rounded text-white/40">
                {langIcon}
              </span>
              <span className="text-[10px] font-mono text-white/40">
                {(sigmoid(source.rerank_score) * 100).toFixed(0)}% match
              </span>
            </div>

            {/* Score bars */}
            <div className="mt-2 space-y-1">
              <ScoreBar
                label="Rerank"
                value={sigmoid(source.rerank_score)}
                color="bg-[var(--color-accent)]"
              />
              {source.dense_score !== undefined && (
                <ScoreBar
                  label="Dense"
                  value={sigmoid(source.dense_score)}
                  color="bg-blue-500"
                />
              )}
              {source.sparse_score !== undefined && (
                <ScoreBar
                  label="Sparse"
                  value={sigmoid(source.sparse_score)}
                  color="bg-emerald-500"
                />
              )}
            </div>
          </div>

          <ChevronDown
            size={12}
            className={cn(
              "shrink-0 text-white/25 transition-transform mt-1",
              expanded && "rotate-180"
            )}
          />
        </div>
      </div>

      {/* Expanded code preview */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3">
              <div
                className="text-[11px] overflow-x-auto max-h-48 overflow-y-auto rounded border border-[var(--color-border)]"
                dangerouslySetInnerHTML={
                  html
                    ? { __html: html }
                    : undefined
                }
              >
                {!html && (
                  <pre className="p-2 text-white/60 font-mono">
                    <code>{source.text_preview}</code>
                  </pre>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
