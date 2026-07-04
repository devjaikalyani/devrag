"use client";
import { truncatePath, fileLanguage } from "@/lib/utils";
import type { RRFRow } from "@/types";

interface RetrievalTableProps {
  query?: string;
  rows?: RRFRow[];
}

const MOCK_ROWS: RRFRow[] = [
  { chunk_id: "c1", file: "src/retrieval/retriever.py", dense_rank: 1, bm25_rank: 3, fused_rank: 1, rerank_score: 0.94 },
  { chunk_id: "c2", file: "src/pipeline.py", dense_rank: 2, bm25_rank: 1, fused_rank: 2, rerank_score: 0.87 },
  { chunk_id: "c3", file: "src/retrieval/embedder.py", dense_rank: 4, bm25_rank: 2, fused_rank: 3, rerank_score: 0.82 },
  { chunk_id: "c4", file: "src/generation/generator.py", dense_rank: 3, bm25_rank: 5, fused_rank: 4, rerank_score: 0.76 },
  { chunk_id: "c5", file: "src/retrieval/reranker.py", dense_rank: 6, bm25_rank: 4, fused_rank: 5, rerank_score: 0.71 },
];

export function RetrievalTable({ query, rows }: RetrievalTableProps) {
  const data = rows ?? MOCK_ROWS;

  return (
    <div className="p-3 space-y-4">
      {query && (
        <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-bg-overlay)] p-2.5">
          <p className="text-[10px] text-white/35 uppercase tracking-wider font-medium mb-1">
            Rewritten query
          </p>
          <p className="text-xs text-white/70 font-mono leading-relaxed">{query}</p>
        </div>
      )}

      <div>
        <p className="text-[10px] text-white/35 uppercase tracking-wider font-medium mb-2">
          RRF Rankings
        </p>
        <div className="rounded-md border border-[var(--color-border)] overflow-hidden">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="border-b border-[var(--color-border)] bg-white/[0.02]">
                <th className="px-2 py-1.5 text-left font-medium text-white/35">File</th>
                <th className="px-2 py-1.5 text-right font-medium text-white/35 font-mono">Dense</th>
                <th className="px-2 py-1.5 text-right font-medium text-white/35 font-mono">BM25</th>
                <th className="px-2 py-1.5 text-right font-medium text-white/35 font-mono">Fused</th>
                <th className="px-2 py-1.5 text-right font-medium text-white/35 font-mono">Score</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row, i) => (
                <tr
                  key={row.chunk_id}
                  className="border-b border-[var(--color-border)] last:border-0 hover:bg-white/[0.02] transition-colors"
                >
                  <td className="px-2 py-1.5 font-mono text-white/60 truncate max-w-[120px]">
                    {truncatePath(row.file, 24)}
                  </td>
                  <td className="px-2 py-1.5 text-right font-mono text-white/40">#{row.dense_rank}</td>
                  <td className="px-2 py-1.5 text-right font-mono text-white/40">#{row.bm25_rank}</td>
                  <td className="px-2 py-1.5 text-right font-mono text-[var(--color-accent)] font-medium">
                    #{row.fused_rank}
                  </td>
                  <td className="px-2 py-1.5 text-right font-mono text-white/60">
                    {(row.rerank_score * 100).toFixed(0)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
