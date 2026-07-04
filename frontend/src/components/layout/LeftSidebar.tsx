"use client";
import { Plus } from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { RepoItemSkeleton } from "@/components/ui/skeleton";
import { RepoItem } from "@/components/repos/RepoItem";
import { SessionList } from "@/components/repos/SessionList";
import { useAppStore } from "@/lib/store";
import { useRepos } from "@/hooks/useRepos";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

export function LeftSidebar() {
  const { repos, activeRepoKey, activateRepo, removeRepo } = useRepos();
  const { setIngestModalOpen } = useAppStore();

  return (
    <aside className="w-[260px] shrink-0 flex flex-col border-r border-[var(--color-border)] bg-[var(--color-bg-subtle)] h-full overflow-hidden">
      {/* Header */}
      <div className="px-3 pt-4 pb-3 border-b border-[var(--color-border)]">
        <Button
          variant="outline"
          size="sm"
          className="w-full justify-start gap-2 text-white/60 hover:text-white"
          onClick={() => setIngestModalOpen(true)}
        >
          <Plus size={12} />
          Ingest repository
        </Button>
      </div>

      <ScrollArea className="flex-1">
        {/* Repos section */}
        <div className="py-2">
          <div className="px-3 pb-1">
            <span className="text-[10px] font-medium uppercase tracking-wider text-white/25">
              Repositories
            </span>
          </div>

          {repos.length === 0 ? (
            <div className="px-3 py-2 space-y-1">
              <p className="text-[11px] text-white/30">No repositories indexed yet.</p>
              <p className="text-[11px] text-white/20">
                Click "+ Ingest repository" to get started.
              </p>
            </div>
          ) : (
            <div className="px-1">
              {repos.map((repo) => (
                <RepoItem
                  key={repo.key}
                  repo={repo}
                  isActive={repo.key === activeRepoKey}
                  onClick={() => activateRepo(repo.key)}
                  onDelete={() => removeRepo(repo.key)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Separator */}
        <div className="mx-3 h-px bg-[var(--color-border)]" />

        {/* Sessions */}
        <SessionList repoKey={activeRepoKey} />
      </ScrollArea>

      {/* Footer — hint */}
      <div className="px-3 py-2.5 border-t border-[var(--color-border)]">
        <p className="text-[10px] text-white/20">
          <kbd className="font-mono bg-white/[0.06] px-1 py-0.5 rounded text-[9px]">⌘K</kbd> to switch
        </p>
      </div>
    </aside>
  );
}
