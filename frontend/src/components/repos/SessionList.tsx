"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, MoreHorizontal, Pencil, Trash2, Plus } from "lucide-react";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import { useAppStore, useSessionsForRepo } from "@/lib/store";
import { relativeTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface SessionListProps {
  repoKey: string | null;
}

export function SessionList({ repoKey }: SessionListProps) {
  const sessions = useSessionsForRepo(repoKey);
  const { activeSessionId, setActiveSession, deleteSession, renameSession, createSession } = useAppStore();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const handleNewChat = () => {
    if (!repoKey) return;
    const session = createSession(repoKey);
    setActiveSession(session.id);
  };

  const startEdit = (id: string, title: string) => {
    setEditingId(id);
    setEditValue(title);
  };

  const commitEdit = () => {
    if (editingId && editValue.trim()) {
      renameSession(editingId, editValue.trim());
    }
    setEditingId(null);
  };

  return (
    <div className="flex flex-col">
      {/* Section header */}
      <div className="flex items-center justify-between px-3 pt-3 pb-1">
        <span className="text-[10px] font-medium uppercase tracking-wider text-white/25">
          Chats
        </span>
        <button
          onClick={handleNewChat}
          disabled={!repoKey}
          className="p-0.5 rounded text-white/30 hover:text-white/70 hover:bg-white/[0.06] transition-colors disabled:opacity-30"
        >
          <Plus size={12} />
        </button>
      </div>

      {sessions.length === 0 && (
        <p className="px-3 py-2 text-[11px] text-white/25">
          {repoKey ? "No conversations yet." : "Select a repo to start."}
        </p>
      )}

      <AnimatePresence initial={false}>
        {sessions.slice().reverse().map((session) => (
          <motion.div
            key={session.id}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15 }}
            className={cn(
              "group relative flex items-center gap-2 px-3 py-2 cursor-pointer rounded-sm transition-colors",
              session.id === activeSessionId
                ? "bg-white/[0.06] text-white"
                : "text-white/50 hover:bg-white/[0.04] hover:text-white/80"
            )}
            onClick={() => setActiveSession(session.id)}
          >
            <MessageSquare size={11} className="shrink-0 opacity-60" />

            <div className="flex-1 min-w-0">
              {editingId === session.id ? (
                <input
                  autoFocus
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onBlur={commitEdit}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitEdit();
                    if (e.key === "Escape") setEditingId(null);
                    e.stopPropagation();
                  }}
                  onClick={(e) => e.stopPropagation()}
                  className="w-full bg-transparent text-xs text-white outline-none border-b border-[var(--color-accent)]"
                />
              ) : (
                <>
                  <div className="text-xs truncate">{session.title}</div>
                  <div className="text-[10px] text-white/25">{relativeTime(session.updatedAt)}</div>
                </>
              )}
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  className="opacity-0 group-hover:opacity-100 p-1 rounded text-white/40 hover:text-white hover:bg-white/[0.08] transition-colors shrink-0"
                  onClick={(e) => e.stopPropagation()}
                >
                  <MoreHorizontal size={11} />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={(e) => { e.stopPropagation(); startEdit(session.id, session.title); }}>
                  <Pencil size={10} /> Rename
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="text-red-400 focus:text-red-400 focus:bg-red-500/10"
                  onClick={(e) => { e.stopPropagation(); deleteSession(session.id); }}
                >
                  <Trash2 size={10} /> Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
