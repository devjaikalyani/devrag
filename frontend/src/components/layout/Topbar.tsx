"use client";
import { useEffect } from "react";
import { Terminal, GitBranch, ChevronDown, BarChart2, Settings } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { useAppStore, useActiveRepo } from "@/lib/store";
import { cn } from "@/lib/utils";

const MLFLOW_URL = process.env.NEXT_PUBLIC_MLFLOW_URL ?? "http://localhost:5000";
const API_DOCS_URL = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001"}/docs`;

async function openMLflow() {
  try {
    await fetch(MLFLOW_URL, { mode: "no-cors", signal: AbortSignal.timeout(2000) });
    window.open(MLFLOW_URL, "_blank");
  } catch {
    toast.error("MLflow is not running. Start it with ./start.sh", { duration: 4000 });
  }
}

export function Topbar() {
  const { setCommandPaletteOpen, setIngestModalOpen } = useAppStore();
  const activeRepo = useActiveRepo();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandPaletteOpen(true);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [setCommandPaletteOpen]);

  return (
    <header className="flex items-center h-11 px-4 border-b border-border bg-bg-subtle shrink-0 gap-3">
      {/* Logo */}
      <div className="flex items-center gap-2 shrink-0">
        <div className="h-5 w-5 rounded bg-accent flex items-center justify-center">
          <Terminal size={11} className="text-white" />
        </div>
        <span className="text-sm font-semibold text-white tracking-tight font-mono">
          DevRAG
        </span>
      </div>

      <nav className="flex items-center gap-1 shrink-0 ml-1">
        <a
          href="/"
          className="px-2 py-0.5 rounded text-xs font-mono text-white/60 hover:text-white hover:bg-white/5 transition-colors"
        >
          Chat
        </a>
        <a
          href="/agent"
          className="px-2 py-0.5 rounded text-xs font-mono text-white/60 hover:text-white hover:bg-white/5 transition-colors"
        >
          Agent
        </a>
      </nav>

      <div className="h-4 w-px bg-white/10 shrink-0" />

      {/* Active repo pill */}
      {activeRepo ? (
        <button
          type="button"
          onClick={() => setCommandPaletteOpen(true)}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded border shrink-0 max-w-[320px]",
            "border-border-strong bg-accent-dim text-accent text-xs font-mono",
            "hover:bg-accent/20 hover:border-accent/50 transition-colors"
          )}
        >
          <GitBranch size={10} className="shrink-0" />
          {activeRepo.owner && (
            <span className="text-accent/60 truncate">{activeRepo.owner}/</span>
          )}
          <span className="font-medium truncate">{activeRepo.name}</span>
          <span className="text-accent/40 text-[10px] shrink-0">
            · {activeRepo.chunkCount.toLocaleString()} chunks
          </span>
          <ChevronDown size={9} className="opacity-50 shrink-0" />
        </button>
      ) : (
        <button
          type="button"
          onClick={() => setIngestModalOpen(true)}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded border border-dashed border-white/10 text-xs text-white/25 hover:text-white/50 hover:border-white/20 transition-colors font-mono shrink-0"
        >
          No repository selected
        </button>
      )}

      <div className="flex-1" />

      {/* Right actions */}
      <div className="flex items-center gap-0.5 shrink-0">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="text-white/30 hover:text-white/70"
              onClick={openMLflow}
            >
              <BarChart2 size={14} />
            </Button>
          </TooltipTrigger>
          <TooltipContent>MLflow dashboard · localhost:5000</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="text-white/30 hover:text-white/70"
              onClick={() => window.open(API_DOCS_URL, "_blank")}
            >
              <Settings size={14} />
            </Button>
          </TooltipTrigger>
          <TooltipContent>API docs · localhost:8001/docs</TooltipContent>
        </Tooltip>

        <div className="ml-2 flex items-center px-2 py-0.5 rounded border border-white/[0.07] text-[10px] text-white/20 font-mono select-none">
          <kbd>⌘K</kbd>
        </div>
      </div>
    </header>
  );
}
