"use client";
import { useState, useCallback } from "react";
import { toast } from "sonner";
import { ingestGitHub, ingestDirectory, getIndexStats } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { IngestProgress } from "@/types";

export function useIngest() {
  const [progress, setProgress] = useState<IngestProgress>({
    status: "idle",
    message: "",
  });
  const [loading, setLoading] = useState(false);
  const { addRepo, setActiveRepo, syncReposFromStats } = useAppStore();

  const reset = useCallback(() => {
    setProgress({ status: "idle", message: "" });
    setLoading(false);
  }, []);

  const refreshStats = useCallback(async () => {
    try {
      const stats = await getIndexStats();
      syncReposFromStats(stats.ingested_sources, stats.active_key, stats.total_chunks);
    } catch {}
  }, [syncReposFromStats]);

  const ingestGitHubRepo = useCallback(async (url: string, branch = "main") => {
    setLoading(true);
    setProgress({ status: "cloning", message: "Cloning repository…" });

    try {
      setProgress({ status: "chunking", message: "Parsing and chunking files…" });
      const result = await ingestGitHub(url, branch);

      const chunkCount = result.new_chunks ?? result.total_chunks ?? 0;

      setProgress({
        status: "embedding",
        message: "Building embeddings…",
        chunks_parsed: chunkCount,
      });
      await new Promise((r) => setTimeout(r, 400));

      setProgress({
        status: "bm25",
        message: "Building BM25 index…",
        chunks_parsed: chunkCount,
        embeddings_done: chunkCount,
      });
      await new Promise((r) => setTimeout(r, 250));

      const statusMsg = result.status === "skipped"
        ? result.reason ?? "Already indexed — switched active repo"
        : `Indexed ${chunkCount} chunks`;

      setProgress({
        status: "done",
        message: statusMsg,
        chunks_parsed: chunkCount,
        embeddings_done: chunkCount,
      });

      // Sync repos from backend (source of truth)
      await refreshStats();

      toast.success(statusMsg);
      return result;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Ingest failed";
      setProgress({ status: "error", message: msg, error: msg });
      throw err;
    } finally {
      setLoading(false);
    }
  }, [refreshStats]);

  const ingestLocalPath = useCallback(async (path: string) => {
    setLoading(true);
    setProgress({ status: "chunking", message: "Parsing local directory…" });

    try {
      const result = await ingestDirectory(path);
      const chunkCount = result.new_chunks ?? result.total_chunks ?? 0;

      setProgress({
        status: "done",
        message: `Indexed ${chunkCount} chunks`,
        chunks_parsed: chunkCount,
        embeddings_done: chunkCount,
      });

      await refreshStats();

      toast.success(`Directory indexed — ${chunkCount} chunks`);
      return result;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Ingest failed";
      setProgress({ status: "error", message: msg, error: msg });
      throw err;
    } finally {
      setLoading(false);
    }
  }, [refreshStats]);

  return { progress, loading, ingestGitHubRepo, ingestLocalPath, reset };
}
