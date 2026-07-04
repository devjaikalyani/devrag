import { create } from "zustand";
import { persist } from "zustand/middleware";
import { generateId } from "./utils";
import type { Repo, ChatSession, ChatMessage, RightPanelTab, Citation, IngestedSource } from "@/types";

interface UIState {
  rightPanelTab: RightPanelTab;
  rightPanelOpen: boolean;
  activeCitationId: number | null;
  commandPaletteOpen: boolean;
  ingestModalOpen: boolean;
}

interface AppState {
  // Repos
  repos: Repo[];
  activeRepoKey: string | null;

  // Sessions
  sessions: ChatSession[];
  activeSessionId: string | null;

  // UI
  ui: UIState;

  // Actions — repos
  addRepo: (repo: Repo) => void;
  removeRepo: (key: string) => void;
  setActiveRepo: (key: string | null) => void;
  updateRepo: (key: string, updates: Partial<Repo>) => void;
  syncReposFromStats: (sources: IngestedSource[], activeKey: string | null, totalChunks: number) => void;

  // Actions — sessions
  createSession: (repoKey: string) => ChatSession;
  deleteSession: (id: string) => void;
  renameSession: (id: string, title: string) => void;
  setActiveSession: (id: string | null) => void;
  addMessage: (sessionId: string, msg: ChatMessage) => void;
  updateMessage: (sessionId: string, msgId: string, updates: Partial<ChatMessage>) => void;
  appendToken: (sessionId: string, msgId: string, token: string) => void;

  // Actions — UI
  setRightPanelTab: (tab: RightPanelTab) => void;
  setRightPanelOpen: (open: boolean) => void;
  setActiveCitation: (id: number | null) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setIngestModalOpen: (open: boolean) => void;
}

function deriveTitle(content: string): string {
  return content.slice(0, 48) + (content.length > 48 ? "…" : "");
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      repos: [],
      activeRepoKey: null,
      sessions: [],
      activeSessionId: null,
      ui: {
        rightPanelTab: "sources",
        rightPanelOpen: true,
        activeCitationId: null,
        commandPaletteOpen: false,
        ingestModalOpen: false,
      },

      // Repos
      addRepo: (repo) =>
        set((s) => ({
          repos: s.repos.find((r) => r.key === repo.key)
            ? s.repos.map((r) => (r.key === repo.key ? repo : r))
            : [...s.repos, repo],
        })),

      removeRepo: (key) =>
        set((s) => ({
          repos: s.repos.filter((r) => r.key !== key),
          activeRepoKey: s.activeRepoKey === key ? null : s.activeRepoKey,
          sessions: s.sessions.filter((sess) => sess.repoKey !== key),
          activeSessionId:
            s.sessions.find((sess) => sess.id === s.activeSessionId)?.repoKey === key
              ? null
              : s.activeSessionId,
        })),

      setActiveRepo: (key) =>
        set((s) => ({
          activeRepoKey: key,
          repos: s.repos.map((r) => ({ ...r, isActive: r.key === key })),
        })),

      updateRepo: (key, updates) =>
        set((s) => ({
          repos: s.repos.map((r) => (r.key === key ? { ...r, ...updates } : r)),
        })),

      syncReposFromStats: (sources, activeKey, totalChunks) => {
        const { repos, addRepo, setActiveRepo } = get();
        sources.forEach((src) => {
          if (!repos.find((r) => r.key === src.key)) {
            const nameParts = src.display_name.split(" (");
            addRepo({
              key: src.key,
              name: nameParts[0] ?? src.key,
              owner: src.identifier.includes("github.com")
                ? src.identifier.split("github.com/")[1]?.split("/")[0]
                : undefined,
              url: src.type === "github" ? src.identifier.split("@")[0] : undefined,
              chunkCount: src.chunk_count,
              lastIndexed: src.ingested_at,
              isActive: src.key === activeKey,
            });
          }
        });
        if (activeKey) setActiveRepo(activeKey);
      },

      // Sessions
      createSession: (repoKey) => {
        const session: ChatSession = {
          id: generateId(),
          repoKey,
          title: "New conversation",
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          messages: [],
        };
        set((s) => ({
          sessions: [...s.sessions, session],
          activeSessionId: session.id,
        }));
        return session;
      },

      deleteSession: (id) =>
        set((s) => ({
          sessions: s.sessions.filter((sess) => sess.id !== id),
          activeSessionId: s.activeSessionId === id ? null : s.activeSessionId,
        })),

      renameSession: (id, title) =>
        set((s) => ({
          sessions: s.sessions.map((sess) =>
            sess.id === id ? { ...sess, title } : sess
          ),
        })),

      setActiveSession: (id) => set({ activeSessionId: id }),

      addMessage: (sessionId, msg) =>
        set((s) => ({
          sessions: s.sessions.map((sess) => {
            if (sess.id !== sessionId) return sess;
            const messages = [...sess.messages, msg];
            const title =
              sess.messages.length === 0 && msg.role === "user"
                ? deriveTitle(msg.content)
                : sess.title;
            return { ...sess, messages, title, updatedAt: new Date().toISOString() };
          }),
        })),

      updateMessage: (sessionId, msgId, updates) =>
        set((s) => ({
          sessions: s.sessions.map((sess) => {
            if (sess.id !== sessionId) return sess;
            return {
              ...sess,
              messages: sess.messages.map((m) =>
                m.id === msgId ? { ...m, ...updates } : m
              ),
            };
          }),
        })),

      appendToken: (sessionId, msgId, token) =>
        set((s) => ({
          sessions: s.sessions.map((sess) => {
            if (sess.id !== sessionId) return sess;
            return {
              ...sess,
              messages: sess.messages.map((m) =>
                m.id === msgId ? { ...m, content: m.content + token } : m
              ),
            };
          }),
        })),

      // UI
      setRightPanelTab: (tab) =>
        set((s) => ({ ui: { ...s.ui, rightPanelTab: tab } })),

      setRightPanelOpen: (open) =>
        set((s) => ({ ui: { ...s.ui, rightPanelOpen: open } })),

      setActiveCitation: (id) =>
        set((s) => ({ ui: { ...s.ui, activeCitationId: id } })),

      setCommandPaletteOpen: (open) =>
        set((s) => ({ ui: { ...s.ui, commandPaletteOpen: open } })),

      setIngestModalOpen: (open) =>
        set((s) => ({ ui: { ...s.ui, ingestModalOpen: open } })),
    }),
    {
      name: "devrag-store",
      partialize: (s) => ({
        repos: s.repos,
        sessions: s.sessions,
        activeRepoKey: s.activeRepoKey,
        activeSessionId: s.activeSessionId,
      }),
    }
  )
);

export const useActiveSession = () => {
  const sessions = useAppStore((s) => s.sessions);
  const activeSessionId = useAppStore((s) => s.activeSessionId);
  return sessions.find((sess) => sess.id === activeSessionId) ?? null;
};

export const useActiveRepo = () => {
  const repos = useAppStore((s) => s.repos);
  const activeRepoKey = useAppStore((s) => s.activeRepoKey);
  return repos.find((r) => r.key === activeRepoKey) ?? null;
};

export const useSessionsForRepo = (repoKey: string | null) => {
  const sessions = useAppStore((s) => s.sessions);
  if (!repoKey) return [];
  return sessions.filter((s) => s.repoKey === repoKey);
};
