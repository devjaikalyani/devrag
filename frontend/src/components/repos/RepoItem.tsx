"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { GitBranch, MoreHorizontal, RefreshCw, Trash2, Copy } from "lucide-react";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { cn, relativeTime } from "@/lib/utils";
import type { Repo } from "@/types";

interface RepoItemProps {
  repo: Repo;
  isActive: boolean;
  onClick: () => void;
  onDelete: () => void;
  onReindex?: () => void;
}

export function RepoItem({ repo, isActive, onClick, onDelete, onReindex }: RepoItemProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const name = repo.name;
  const owner = repo.owner ?? "";

  return (
    <motion.div
      layout
      className={cn(
        "group relative flex items-start gap-2.5 px-3 py-2.5 cursor-pointer transition-colors rounded-sm",
        isActive
          ? "bg-[var(--color-accent-dim)] text-white"
          : "text-white/60 hover:bg-white/[0.04] hover:text-white"
      )}
      onClick={onClick}
    >
      {/* Active indicator bar */}
      {isActive && (
        <motion.div
          layoutId="active-repo-bar"
          className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full bg-[var(--color-accent)]"
        />
      )}

      <GitBranch size={13} className="mt-0.5 shrink-0 opacity-70" />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-xs font-medium truncate">{name}</span>
        </div>
        {owner && (
          <div className="text-[10px] text-white/35 font-mono truncate">{owner}</div>
        )}
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[10px] text-white/30">
            {repo.chunkCount.toLocaleString()} chunks
          </span>
          <span className="text-[10px] text-white/20">·</span>
          <span className="text-[10px] text-white/30">{relativeTime(repo.lastIndexed)}</span>
        </div>
      </div>

      <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
        <DropdownMenuTrigger asChild>
          <button
            className={cn(
              "p-1 rounded transition-opacity shrink-0",
              "opacity-0 group-hover:opacity-100",
              menuOpen && "opacity-100",
              "hover:bg-white/[0.08] text-white/50 hover:text-white"
            )}
            onClick={(e) => e.stopPropagation()}
          >
            <MoreHorizontal size={12} />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-[148px]">
          <DropdownMenuLabel>Repository</DropdownMenuLabel>
          {onReindex && (
            <DropdownMenuItem
              onClick={(e) => { e.stopPropagation(); onReindex(); setMenuOpen(false); }}
            >
              <RefreshCw size={11} />
              Re-index
            </DropdownMenuItem>
          )}
          <DropdownMenuItem
            onClick={(e) => {
              e.stopPropagation();
              navigator.clipboard.writeText(repo.key);
              setMenuOpen(false);
            }}
          >
            <Copy size={11} />
            Copy ID
          </DropdownMenuItem>
          <DropdownMenuSeparator className="my-1 h-px bg-[var(--color-border)]" />
          <DropdownMenuItem
            className="text-red-400 focus:text-red-400 focus:bg-red-500/10"
            onClick={(e) => { e.stopPropagation(); onDelete(); setMenuOpen(false); }}
          >
            <Trash2 size={11} />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </motion.div>
  );
}
