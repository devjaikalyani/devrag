"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { GitBranch, FolderOpen, CheckCircle2, AlertCircle, Loader2, ChevronRight } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogBody, DialogFooter
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useIngest } from "@/hooks/useIngest";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { IngestProgress } from "@/types";

const STEP_LABELS: Record<IngestProgress["status"], string> = {
  idle: "",
  cloning: "Cloning repository",
  chunking: "Parsing & chunking",
  embedding: "Building embeddings",
  bm25: "Building BM25 index",
  done: "Complete",
  error: "Failed",
};

const STEPS: IngestProgress["status"][] = ["cloning", "chunking", "embedding", "bm25", "done"];

function ProgressSteps({ status, chunks, embeddings }: {
  status: IngestProgress["status"];
  chunks?: number;
  embeddings?: number;
}) {
  const currentIdx = STEPS.indexOf(status);

  return (
    <div className="space-y-1.5 mt-4">
      {STEPS.filter(s => s !== "done").map((step, i) => {
        const isDone = currentIdx > i || status === "done";
        const isActive = STEPS[currentIdx] === step;
        const isPending = currentIdx < i && status !== "done";

        return (
          <motion.div
            key={step}
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.06 }}
            className={cn(
              "flex items-center gap-2.5 px-3 py-2 rounded-md text-xs transition-colors",
              isDone && "bg-green-500/[0.06] text-green-400",
              isActive && "bg-[var(--color-accent-dim)] text-[var(--color-accent)]",
              isPending && "text-white/25"
            )}
          >
            {isDone ? (
              <CheckCircle2 size={12} className="shrink-0" />
            ) : isActive ? (
              <Loader2 size={12} className="shrink-0 animate-spin" />
            ) : (
              <div className="w-3 h-3 rounded-full border border-current shrink-0 opacity-30" />
            )}
            <span>{STEP_LABELS[step]}</span>
            {isActive && step === "embedding" && chunks && (
              <span className="ml-auto font-mono text-[10px] opacity-70">
                {chunks} chunks
              </span>
            )}
            {isDone && step === "bm25" && embeddings && (
              <span className="ml-auto font-mono text-[10px] opacity-60">
                {embeddings} vectors
              </span>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}

export function IngestModal() {
  const { ui, setIngestModalOpen } = useAppStore();
  const { progress, loading, ingestGitHubRepo, ingestLocalPath, reset } = useIngest();
  const [tab, setTab] = useState("github");
  const [githubUrl, setGithubUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [localPath, setLocalPath] = useState("");

  const handleOpenChange = (open: boolean) => {
    if (!loading) {
      setIngestModalOpen(open);
      if (!open) {
        reset();
        setGithubUrl("");
        setLocalPath("");
        setBranch("main");
      }
    }
  };

  const handleSubmit = async () => {
    try {
      if (tab === "github") {
        await ingestGitHubRepo(githubUrl, branch);
      } else {
        await ingestLocalPath(localPath);
      }
      setTimeout(() => handleOpenChange(false), 1200);
    } catch {}
  };

  const isDone = progress.status === "done";
  const isError = progress.status === "error";
  const isRunning = loading && !isDone && !isError;
  const canSubmit = tab === "github" ? githubUrl.trim().length > 0 : localPath.trim().length > 0;

  return (
    <Dialog open={ui.ingestModalOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Ingest repository</DialogTitle>
          <DialogDescription>
            Index a codebase to start asking questions about it.
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="pt-3 pb-2">
          {progress.status === "idle" ? (
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList className="mb-4">
                <TabsTrigger value="github">
                  <GitBranch size={11} className="mr-1" />
                  GitHub URL
                </TabsTrigger>
                <TabsTrigger value="local">
                  <FolderOpen size={11} className="mr-1" />
                  Local path
                </TabsTrigger>
              </TabsList>

              <TabsContent value="github" className="space-y-3">
                <div>
                  <label className="text-[11px] text-white/50 mb-1.5 block">Repository URL</label>
                  <Input
                    placeholder="https://github.com/owner/repo"
                    value={githubUrl}
                    onChange={(e) => setGithubUrl(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && canSubmit && handleSubmit()}
                    className="font-mono text-xs"
                    autoFocus
                  />
                </div>
                <div>
                  <label className="text-[11px] text-white/50 mb-1.5 block">Branch</label>
                  <Input
                    placeholder="main"
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    className="font-mono text-xs"
                  />
                </div>

                <div className="rounded-md bg-[var(--color-bg-overlay)] border border-[var(--color-border)] p-3 space-y-1">
                  <p className="text-[11px] text-white/50 font-medium">Example repos to try</p>
                  {[
                    "https://github.com/tiangolo/fastapi",
                    "https://github.com/vercel/next.js",
                    "https://github.com/vitejs/vite",
                  ].map((url) => (
                    <button
                      key={url}
                      onClick={() => setGithubUrl(url)}
                      className="flex items-center gap-1 text-[11px] font-mono text-white/40 hover:text-[var(--color-accent)] transition-colors"
                    >
                      <ChevronRight size={10} />
                      {url.replace("https://github.com/", "")}
                    </button>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="local" className="space-y-3">
                <div>
                  <label className="text-[11px] text-white/50 mb-1.5 block">Absolute path</label>
                  <Input
                    placeholder="/Users/you/projects/myrepo"
                    value={localPath}
                    onChange={(e) => setLocalPath(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && canSubmit && handleSubmit()}
                    className="font-mono text-xs"
                    autoFocus
                  />
                </div>
                <p className="text-[11px] text-white/35">
                  Must be accessible from the backend server.
                </p>
              </TabsContent>
            </Tabs>
          ) : (
            <AnimatePresence mode="wait">
              <motion.div
                key={progress.status}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="py-2"
              >
                {isDone ? (
                  <div className="flex flex-col items-center gap-3 py-4">
                    <motion.div
                      initial={{ scale: 0.5, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ type: "spring", stiffness: 300 }}
                    >
                      <CheckCircle2 size={32} className="text-green-400" />
                    </motion.div>
                    <p className="text-sm text-white/80">{progress.message}</p>
                  </div>
                ) : isError ? (
                  <div className="flex flex-col items-center gap-3 py-4">
                    <AlertCircle size={32} className="text-red-400" />
                    <p className="text-sm text-red-400">{progress.message}</p>
                  </div>
                ) : (
                  <>
                    <p className="text-xs text-white/50">{progress.message}</p>
                    <ProgressSteps
                      status={progress.status}
                      chunks={progress.chunks_parsed}
                      embeddings={progress.embeddings_done}
                    />
                  </>
                )}
              </motion.div>
            </AnimatePresence>
          )}
        </DialogBody>

        <DialogFooter>
          <Button variant="ghost" size="sm" onClick={() => handleOpenChange(false)} disabled={loading && !isDone}>
            {isDone ? "Close" : "Cancel"}
          </Button>
          {progress.status === "idle" && (
            <Button
              size="sm"
              onClick={handleSubmit}
              disabled={!canSubmit || loading}
            >
              {loading && <Loader2 size={12} className="animate-spin" />}
              Index repository
            </Button>
          )}
          {isError && (
            <Button size="sm" variant="outline" onClick={reset}>
              Retry
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
