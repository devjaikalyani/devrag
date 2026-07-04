"use client";
import { motion } from "framer-motion";
import type { TraceData } from "@/types";

const MOCK_TRACE: TraceData = {
  message_id: "demo",
  embed_ms: 28,
  retrieve_ms: 142,
  rerank_ms: 89,
  generate_ms: 1340,
  nli_ms: 67,
  total_ms: 1666,
};

const SEGMENTS = [
  { key: "embed_ms" as const, label: "Embed query", color: "bg-blue-500" },
  { key: "retrieve_ms" as const, label: "Retrieve (hybrid)", color: "bg-purple-500" },
  { key: "rerank_ms" as const, label: "Rerank", color: "bg-[var(--color-accent)]" },
  { key: "generate_ms" as const, label: "Generate (LLM)", color: "bg-emerald-500" },
  { key: "nli_ms" as const, label: "Faithfulness (NLI)", color: "bg-amber-500" },
];

interface TraceWaterfallProps {
  trace?: TraceData;
}

export function TraceWaterfall({ trace }: TraceWaterfallProps) {
  const data = trace ?? MOCK_TRACE;
  const total = data.total_ms;

  // Compute cumulative offsets
  let offset = 0;
  const bars = SEGMENTS.map((seg) => {
    const ms = data[seg.key];
    const pct = (ms / total) * 100;
    const result = { ...seg, ms, pct, offset };
    offset += pct;
    return result;
  });

  return (
    <div className="p-3 space-y-4">
      {/* Waterfall chart */}
      <div>
        <p className="text-[10px] text-white/35 uppercase tracking-wider font-medium mb-3">
          Latency breakdown · {total}ms total
        </p>

        {/* Horizontal stacked bar */}
        <div className="relative h-5 rounded overflow-hidden bg-white/[0.04] mb-4">
          {bars.map((bar) => (
            <motion.div
              key={bar.key}
              initial={{ width: 0 }}
              animate={{ width: `${bar.pct}%` }}
              transition={{ duration: 0.4, delay: bars.indexOf(bar) * 0.06, ease: "easeOut" }}
              className={`absolute top-0 bottom-0 ${bar.color} opacity-80`}
              style={{ left: `${bar.offset}%` }}
            />
          ))}
        </div>

        {/* Per-segment rows */}
        <div className="space-y-2">
          {bars.map((bar) => (
            <div key={bar.key} className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-sm shrink-0 ${bar.color}`} />
              <span className="text-xs text-white/60 flex-1">{bar.label}</span>
              <span className="font-mono text-[11px] text-white/40">{bar.ms}ms</span>
              <div className="w-20 h-1.5 rounded bg-white/[0.04] overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${bar.pct}%` }}
                  transition={{ duration: 0.5, delay: bars.indexOf(bar) * 0.06 }}
                  className={`h-full ${bar.color} opacity-70`}
                />
              </div>
              <span className="font-mono text-[10px] text-white/25 w-9 text-right">
                {bar.pct.toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Total */}
      <div className="rounded-md border border-[var(--color-border)] p-2.5 flex justify-between">
        <span className="text-xs text-white/40">Total latency</span>
        <span className="font-mono text-sm text-white/80 font-medium">{total}ms</span>
      </div>

      {trace === undefined && (
        <p className="text-[11px] text-white/25 italic text-center">
          Demo trace — send a query to see real timing
        </p>
      )}
    </div>
  );
}
