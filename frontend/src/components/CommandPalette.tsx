"use client";
import { useEffect, useState } from "react";
import { Command } from "cmdk";
import { motion, AnimatePresence } from "framer-motion";
import { GitBranch, MessageSquare, Hash, Plus, Search } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { useRepos } from "@/hooks/useRepos";
import { cn } from "@/lib/utils";

export function CommandPalette() {
  const { ui, setCommandPaletteOpen, setActiveSession, createSession, setIngestModalOpen } =
    useAppStore();
  const { repos, activateRepo } = useRepos();
  const sessions = useAppStore((s) => s.sessions);
  const activeRepoKey = useAppStore((s) => s.activeRepoKey);
  const [search, setSearch] = useState("");

  const close = () => {
    setCommandPaletteOpen(false);
    setSearch("");
  };

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    if (ui.commandPaletteOpen) {
      document.addEventListener("keydown", handler);
    }
    return () => document.removeEventListener("keydown", handler);
  }, [ui.commandPaletteOpen]);

  const handleSelectRepo = (key: string) => {
    activateRepo(key);
    close();
  };

  const handleSelectSession = (id: string) => {
    setActiveSession(id);
    close();
  };

  const handleNewChat = () => {
    if (activeRepoKey) {
      createSession(activeRepoKey);
    }
    close();
  };

  return (
    <AnimatePresence>
      {ui.commandPaletteOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
            onClick={close}
          />

          {/* Palette */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -8 }}
            transition={{ duration: 0.14 }}
            className="fixed left-1/2 top-[18%] -translate-x-1/2 z-50 w-full max-w-[520px] shadow-2xl"
          >
            <Command
              className="rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] overflow-hidden"
              shouldFilter={true}
              onKeyDown={(e) => e.key === "Escape" && close()}
            >
              <div className="flex items-center gap-2 px-3 border-b border-[var(--color-border)]">
                <Search size={13} className="text-white/30 shrink-0" />
                <Command.Input
                  value={search}
                  onValueChange={setSearch}
                  placeholder="Switch repo, jump to chat, search…"
                  className="flex-1 bg-transparent py-3 text-sm text-white placeholder:text-white/30 outline-none"
                  autoFocus
                />
                <kbd className="text-[9px] font-mono text-white/20 bg-white/[0.06] px-1.5 py-0.5 rounded">
                  ESC
                </kbd>
              </div>

              <Command.List className="max-h-[380px] overflow-y-auto p-1.5">
                <Command.Empty className="py-8 text-center text-sm text-white/30">
                  No results found.
                </Command.Empty>

                {/* Actions */}
                <Command.Group
                  heading="Actions"
                  className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-white/25"
                >
                  <Command.Item
                    value="new chat"
                    onSelect={handleNewChat}
                    className={cn(
                      "flex items-center gap-2.5 px-2 py-2 rounded-md cursor-pointer text-sm text-white/70",
                      "aria-selected:bg-[var(--color-accent-dim)] aria-selected:text-white",
                      "transition-colors"
                    )}
                  >
                    <Plus size={12} />
                    New chat
                  </Command.Item>
                  <Command.Item
                    value="ingest repository"
                    onSelect={() => { setIngestModalOpen(true); close(); }}
                    className={cn(
                      "flex items-center gap-2.5 px-2 py-2 rounded-md cursor-pointer text-sm text-white/70",
                      "aria-selected:bg-[var(--color-accent-dim)] aria-selected:text-white",
                      "transition-colors"
                    )}
                  >
                    <Plus size={12} />
                    Ingest repository
                  </Command.Item>
                </Command.Group>

                {/* Repos */}
                {repos.length > 0 && (
                  <Command.Group
                    heading="Repositories"
                    className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-white/25"
                  >
                    {repos.map((repo) => (
                      <Command.Item
                        key={repo.key}
                        value={`repo ${repo.name} ${repo.owner ?? ""} ${repo.key}`}
                        onSelect={() => handleSelectRepo(repo.key)}
                        className={cn(
                          "flex items-center gap-2.5 px-2 py-2 rounded-md cursor-pointer text-sm transition-colors",
                          repo.key === activeRepoKey
                            ? "text-[var(--color-accent)]"
                            : "text-white/70",
                          "aria-selected:bg-[var(--color-accent-dim)] aria-selected:text-white"
                        )}
                      >
                        <GitBranch size={12} className="shrink-0" />
                        <span className="font-mono">
                          {repo.owner && <span className="text-white/40">{repo.owner}/</span>}
                          {repo.name}
                        </span>
                        <span className="ml-auto text-[10px] font-mono text-white/25">
                          {repo.chunkCount.toLocaleString()} chunks
                        </span>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}

                {/* Recent sessions */}
                {sessions.length > 0 && (
                  <Command.Group
                    heading="Recent chats"
                    className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-white/25"
                  >
                    {sessions.slice(-8).reverse().map((sess) => (
                      <Command.Item
                        key={sess.id}
                        value={`session ${sess.title} ${sess.repoKey}`}
                        onSelect={() => handleSelectSession(sess.id)}
                        className={cn(
                          "flex items-center gap-2.5 px-2 py-2 rounded-md cursor-pointer text-sm text-white/70",
                          "aria-selected:bg-[var(--color-accent-dim)] aria-selected:text-white",
                          "transition-colors"
                        )}
                      >
                        <MessageSquare size={12} className="shrink-0" />
                        <span className="truncate">{sess.title}</span>
                        <span className="ml-auto text-[10px] font-mono text-white/25 shrink-0">
                          {sess.repoKey.split("__")[1] ?? sess.repoKey}
                        </span>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}
              </Command.List>
            </Command>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
