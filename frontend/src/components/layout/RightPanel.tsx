"use client";
import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { PanelRight } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SourceCard } from "@/components/sources/SourceCard";
import { RetrievalTable } from "@/components/sources/RetrievalTable";
import { TraceWaterfall } from "@/components/sources/TraceWaterfall";
import { SourceCardSkeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useAppStore, useActiveSession } from "@/lib/store";
import { cn } from "@/lib/utils";

export function RightPanel() {
  const { ui, setRightPanelTab, setRightPanelOpen, setActiveCitation } = useAppStore();
  const activeSession = useActiveSession();
  const citationRefs = useRef<Record<number, HTMLDivElement>>({});

  // Get last assistant message with sources
  const messages = activeSession?.messages ?? [];
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant" && !m.isStreaming);
  const sources = lastAssistant?.sources ?? [];
  const isLoading = messages.some((m) => m.isStreaming);

  // Scroll to active citation
  useEffect(() => {
    if (ui.activeCitationId !== null) {
      const el = document.getElementById(`source-${ui.activeCitationId}`);
      el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [ui.activeCitationId]);

  // Auto-open panel when sources arrive
  useEffect(() => {
    if (sources.length > 0 && !ui.rightPanelOpen) {
      setRightPanelOpen(true);
    }
  }, [sources.length]);

  return (
    <AnimatePresence initial={false}>
      {ui.rightPanelOpen ? (
        <motion.aside
          key="right-panel"
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: 380, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ duration: 0.22, ease: "easeInOut" }}
          className="shrink-0 flex flex-col border-l border-[var(--color-border)] bg-[var(--color-bg-subtle)] h-full overflow-hidden"
          style={{ minWidth: 0 }}
        >
          <Tabs
            value={ui.rightPanelTab}
            onValueChange={(v) => setRightPanelTab(v as any)}
            className="flex flex-col h-full"
          >
            <div className="flex items-center justify-between pl-1 pr-3 border-b border-[var(--color-border)] shrink-0">
              <TabsList className="border-0">
                <TabsTrigger value="sources">Sources</TabsTrigger>
                <TabsTrigger value="retrieval">Retrieval</TabsTrigger>
                <TabsTrigger value="trace">Trace</TabsTrigger>
              </TabsList>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setRightPanelOpen(false)}
                className="text-white/30 hover:text-white"
              >
                <PanelRight size={13} />
              </Button>
            </div>

            <ScrollArea className="flex-1">
              <TabsContent value="sources">
                {isLoading ? (
                  <>
                    <SourceCardSkeleton />
                    <SourceCardSkeleton />
                    <SourceCardSkeleton />
                  </>
                ) : sources.length === 0 ? (
                  <div className="p-4 text-center py-16">
                    <p className="text-[11px] text-white/25">
                      Source citations will appear here after your first query.
                    </p>
                  </div>
                ) : (
                  sources.map((src, i) => (
                    <SourceCard
                      key={`${src.source}-${i}`}
                      source={src}
                      index={i}
                      isActive={ui.activeCitationId === i + 1}
                      onClick={() => setActiveCitation(i + 1)}
                    />
                  ))
                )}
              </TabsContent>

              <TabsContent value="retrieval">
                <RetrievalTable />
              </TabsContent>

              <TabsContent value="trace">
                <TraceWaterfall />
              </TabsContent>
            </ScrollArea>
          </Tabs>
        </motion.aside>
      ) : (
        <motion.div
          key="right-panel-collapsed"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="shrink-0 border-l border-[var(--color-border)] bg-[var(--color-bg-subtle)] flex flex-col items-center py-3"
          style={{ width: 36 }}
        >
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setRightPanelOpen(true)}
            className="text-white/30 hover:text-white"
            title="Open sources panel"
          >
            <PanelRight size={13} />
          </Button>
          {sources.length > 0 && (
            <span className="mt-1 text-[9px] font-mono text-white/25">{sources.length}</span>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
