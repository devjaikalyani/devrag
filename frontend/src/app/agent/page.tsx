"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bot,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  Clock,
  ExternalLink,
  GitPullRequest,
  Loader2,
  Play,
  XCircle,
} from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  getRuns,
  startSolve,
  streamRunEvents,
  type RunEvent,
  type RunSummary,
} from "@/lib/api";
import { useRepos } from "@/hooks/useRepos";

type Mode = "issue" | "task";

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    queued: "bg-white/5 text-white/50 border-white/10",
    running: "bg-accent-dim text-accent border-accent/30",
    done: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    failed: "bg-red-500/10 text-red-400 border-red-500/30",
  };
  return (
    <Badge variant="outline" className={cn("font-mono text-[10px]", styles[status] ?? styles.queued)}>
      {status}
    </Badge>
  );
}

function EventRow({ event }: { event: RunEvent }) {
  const isNode = event.type === "node";
  const isDone = event.type === "done";
  const isError = event.type === "error";

  return (
    <div className="flex gap-2.5 py-2 border-b border-white/[0.04] last:border-0">
      <div className="mt-0.5 shrink-0">
        {isDone ? (
          <CheckCircle2 size={13} className="text-emerald-400" />
        ) : isError ? (
          <XCircle size={13} className="text-red-400" />
        ) : isNode ? (
          <ChevronRight size={13} className="text-accent" />
        ) : (
          <CircleDashed size={13} className="text-white/25" />
        )}
      </div>
      <div className="min-w-0 flex-1 text-xs">
        <div className={cn("font-mono", isError ? "text-red-400" : isNode ? "text-white/85" : "text-white/45")}>
          {isNode ? event.label ?? event.node : isDone ? "Run complete" : isError ? "Run failed" : event.detail}
        </div>

        {isError && event.error != null && (
          <div className="mt-1 text-red-400/70 font-mono break-words">{String(event.error)}</div>
        )}

        {event.action_plan && event.action_plan.length > 0 && (
          <ol className="mt-1.5 space-y-0.5 text-white/50 list-decimal list-inside">
            {event.action_plan.map((step, i) => (
              <li key={i} className="truncate">{step}</li>
            ))}
          </ol>
        )}

        {event.files_changed && event.files_changed.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {event.files_changed.map((f) => (
              <span key={f} className="px-1.5 py-0.5 rounded bg-white/5 text-white/60 font-mono text-[10px]">
                {f}
              </span>
            ))}
          </div>
        )}

        {event.test_passed !== undefined && event.type === "node" && (
          <div className={cn("mt-1 font-mono text-[11px]", event.test_passed ? "text-emerald-400" : "text-amber-400")}>
            {event.test_passed ? "Tests passed" : "Tests failing"}
          </div>
        )}

        {event.test_output && !event.test_passed && (
          <pre className="mt-1.5 p-2 rounded bg-black/40 text-white/40 text-[10px] overflow-x-auto max-h-32 overflow-y-auto whitespace-pre-wrap">
            {event.test_output}
          </pre>
        )}

        {event.pr_url && (
          <a
            href={event.pr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1.5 inline-flex items-center gap-1.5 text-accent hover:underline font-mono text-[11px]"
          >
            <GitPullRequest size={11} />
            {event.pr_url}
            <ExternalLink size={9} />
          </a>
        )}

        {isDone && (
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-white/40 font-mono text-[10px]">
            {event.cost_usd !== undefined && <span>cost ${Number(event.cost_usd).toFixed(4)}</span>}
            {event.total_tokens !== undefined && Number(event.total_tokens) > 0 && (
              <span>{Number(event.total_tokens).toLocaleString()} tokens</span>
            )}
            {event.elapsed_seconds !== undefined && <span>{String(event.elapsed_seconds)}s</span>}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AgentPage() {
  useRepos();

  const [mode, setMode] = useState<Mode>("issue");
  const [issueUrl, setIssueUrl] = useState("");
  const [repoPath, setRepoPath] = useState("");
  const [task, setTask] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [noPr, setNoPr] = useState(false);

  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [runs, setRuns] = useState<RunSummary[]>([]);

  const closeStream = useRef<(() => void) | null>(null);
  const timelineEnd = useRef<HTMLDivElement>(null);

  const refreshRuns = useCallback(() => {
    getRuns().then((r) => setRuns(r.runs)).catch(() => {});
  }, []);

  useEffect(() => {
    refreshRuns();
    return () => closeStream.current?.();
  }, [refreshRuns]);

  useEffect(() => {
    timelineEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const attachToRun = useCallback((runId: string) => {
    closeStream.current?.();
    setActiveRunId(runId);
    setEvents([]);
    setStreaming(true);
    closeStream.current = streamRunEvents(
      runId,
      (event) => setEvents((prev) => [...prev, event]),
      () => {
        setStreaming(false);
        refreshRuns();
      },
      () => {
        setStreaming(false);
        refreshRuns();
      }
    );
  }, [refreshRuns]);

  const canSubmit =
    !streaming &&
    (mode === "issue" ? issueUrl.trim().length > 0 : repoPath.trim().length > 0 && task.trim().length > 0);

  const handleStart = async () => {
    if (!canSubmit) return;
    const req =
      mode === "issue"
        ? { issue_url: issueUrl.trim(), dry_run: dryRun, no_pr: noPr }
        : { repo_path: repoPath.trim(), task: task.trim(), dry_run: dryRun };
    try {
      const { run_id } = await startSolve(req);
      attachToRun(run_id);
      refreshRuns();
    } catch {
      // fetchJSON already surfaced the toast
    }
  };

  return (
    <div className="flex flex-col h-full bg-[var(--color-bg)]">
      <Topbar />

      <div className="flex flex-1 min-h-0">
        {/* Left: run form + history */}
        <aside className="w-[340px] shrink-0 border-r border-border flex flex-col min-h-0">
          <div className="p-4 border-b border-border space-y-3">
            <div className="flex items-center gap-2 text-white/85 text-sm font-medium">
              <Bot size={15} className="text-accent" />
              Autonomous run
            </div>

            {/* Mode toggle */}
            <div className="flex rounded border border-border overflow-hidden text-xs font-mono">
              {(["issue", "task"] as Mode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={cn(
                    "flex-1 px-2 py-1.5 transition-colors",
                    mode === m ? "bg-accent-dim text-accent" : "text-white/40 hover:text-white/70"
                  )}
                >
                  {m === "issue" ? "GitHub issue" : "Local task"}
                </button>
              ))}
            </div>

            {mode === "issue" ? (
              <Input
                value={issueUrl}
                onChange={(e) => setIssueUrl(e.target.value)}
                placeholder="https://github.com/owner/repo/issues/42"
                className="font-mono text-xs"
              />
            ) : (
              <>
                <Input
                  value={repoPath}
                  onChange={(e) => setRepoPath(e.target.value)}
                  placeholder="/path/to/local/repo"
                  className="font-mono text-xs"
                />
                <textarea
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  placeholder="Describe the change: fix the failing divide-by-zero test in calculator.py"
                  rows={3}
                  className="w-full rounded border border-border bg-transparent px-3 py-2 text-xs text-white/85 placeholder:text-white/25 focus:outline-none focus:border-accent/50 resize-none font-mono"
                />
              </>
            )}

            <div className="flex items-center gap-4 text-xs text-white/50">
              <label className="flex items-center gap-1.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                  className="accent-[var(--color-accent)]"
                />
                Dry run (plan only)
              </label>
              {mode === "issue" && (
                <label className="flex items-center gap-1.5 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={noPr}
                    onChange={(e) => setNoPr(e.target.checked)}
                    className="accent-[var(--color-accent)]"
                  />
                  No PR
                </label>
              )}
            </div>

            <Button onClick={handleStart} disabled={!canSubmit} className="w-full gap-2" size="sm">
              {streaming ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
              {streaming ? "Running" : "Start run"}
            </Button>
          </div>

          {/* Run history */}
          <div className="flex-1 min-h-0 overflow-y-auto">
            <div className="px-4 py-2 text-[10px] uppercase tracking-wider text-white/30 font-mono">
              Run history
            </div>
            {runs.length === 0 ? (
              <div className="px-4 py-6 text-xs text-white/25 text-center">No runs yet</div>
            ) : (
              runs.map((run) => (
                <button
                  key={run.id}
                  type="button"
                  onClick={() => attachToRun(run.id)}
                  className={cn(
                    "w-full text-left px-4 py-2.5 border-b border-white/[0.04] hover:bg-white/[0.03] transition-colors",
                    activeRunId === run.id && "bg-white/[0.04]"
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-white/70 font-mono truncate">{run.target}</span>
                    <StatusBadge status={run.status} />
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-white/30 font-mono">
                    <Clock size={9} />
                    {run.created_at}
                    <span className="text-white/20">·</span>
                    {run.mode}
                  </div>
                </button>
              ))
            )}
          </div>
        </aside>

        {/* Right: live timeline */}
        <main className="flex-1 flex flex-col min-w-0 min-h-0">
          {activeRunId ? (
            <>
              <div className="px-5 py-3 border-b border-border flex items-center gap-3">
                <span className="text-xs font-mono text-white/50">run</span>
                <span className="text-xs font-mono text-accent">{activeRunId}</span>
                {streaming && <Loader2 size={12} className="animate-spin text-white/30" />}
              </div>
              <div className="flex-1 overflow-y-auto px-5 py-3">
                {events.length === 0 && (
                  <div className="text-xs text-white/30 font-mono py-4">Waiting for events...</div>
                )}
                {events.map((event, i) => (
                  <EventRow key={i} event={event} />
                ))}
                <div ref={timelineEnd} />
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center px-8">
              <div className="h-10 w-10 rounded-lg bg-accent-dim flex items-center justify-center">
                <Bot size={18} className="text-accent" />
              </div>
              <div className="text-sm text-white/70 font-medium">Hand DevRAG an issue, get back a tested fix</div>
              <p className="text-xs text-white/35 max-w-sm leading-relaxed">
                Point it at a GitHub issue or describe a task against a local repo. The agent plans,
                explores with hybrid retrieval, writes code, runs the tests, and opens a pull request.
                Follow every step live here.
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
