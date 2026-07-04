"use client";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/utils";

interface CitationChipProps {
  id: number;
}

export function CitationChip({ id }: CitationChipProps) {
  const { setActiveCitation, setRightPanelTab, setRightPanelOpen, ui } = useAppStore();

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    setRightPanelOpen(true);
    setRightPanelTab("sources");
    setActiveCitation(id);
  };

  const isActive = ui.activeCitationId === id;

  return (
    <button
      onClick={handleClick}
      className={cn(
        "inline-flex items-center justify-center align-super",
        "h-4 min-w-[16px] px-1 rounded text-[9px] font-mono font-bold leading-none",
        "transition-colors cursor-pointer",
        isActive
          ? "bg-[var(--color-accent)] text-white"
          : "bg-[var(--color-accent-dim)] text-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
      )}
      title={`Source ${id}`}
    >
      {id}
    </button>
  );
}
