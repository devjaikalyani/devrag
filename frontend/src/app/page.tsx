"use client";
import { Topbar } from "@/components/layout/Topbar";
import { LeftSidebar } from "@/components/layout/LeftSidebar";
import { ChatPane } from "@/components/layout/ChatPane";
import { RightPanel } from "@/components/layout/RightPanel";
import { IngestModal } from "@/components/modals/IngestModal";
import { CommandPalette } from "@/components/CommandPalette";
import { useRepos } from "@/hooks/useRepos";

export default function HomePage() {
  useRepos(); // Bootstrap repo sync from backend on load

  return (
    <div className="flex flex-col h-full bg-[var(--color-bg)]">
      <Topbar />

      <div className="flex flex-1 min-h-0">
        {/* Left sidebar */}
        <LeftSidebar />

        {/* Center chat */}
        <main className="flex-1 flex flex-col min-w-0 h-full">
          <ChatPane />
        </main>

        {/* Right sources panel */}
        <RightPanel />
      </div>

      {/* Modals / overlays */}
      <IngestModal />
      <CommandPalette />
    </div>
  );
}
