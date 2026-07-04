"use client";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getIndexStats, switchRepo, deleteRepo as deleteRepoAPI } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { toast } from "sonner";

export function useRepos() {
  const store = useAppStore();

  const { data: stats, refetch } = useQuery({
    queryKey: ["index-stats"],
    queryFn: getIndexStats,
    refetchInterval: 30_000,
    retry: false,
  });

  // Sync repos from backend stats on load
  useEffect(() => {
    if (stats) {
      store.syncReposFromStats(
        stats.ingested_sources,
        stats.active_key,
        stats.total_chunks
      );
    }
  }, [stats]);

  const activateRepo = async (key: string) => {
    try {
      await switchRepo(key);
      store.setActiveRepo(key);
      refetch();
    } catch {
      // toast already shown by api client
    }
  };

  const removeRepo = async (key: string) => {
    try {
      await deleteRepoAPI(key);
      store.removeRepo(key);
      toast.success("Repository removed");
      refetch();
    } catch {}
  };

  return {
    repos: store.repos,
    activeRepoKey: store.activeRepoKey,
    activateRepo,
    removeRepo,
    stats,
  };
}
