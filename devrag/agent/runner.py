"""
runner.py — Orchestrates agent runs and streams progress events.

A run is either:
  - issue mode: a GitHub issue URL (clone, index, fix, test, review, PR)
  - task mode:  a free-text task against an already-ingested local repo
                (index-shared with chat; no PR)

Every run gets an in-memory event queue (consumed by the SSE endpoint or CLI)
and a persisted JSON record under data/runs/.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from devrag.llm.client import usage as llm_usage

RUNS_DIR = Path(__file__).resolve().parents[2] / "data" / "runs"


@dataclass
class Run:
    id: str
    mode: str                      # "issue" | "task"
    target: str                    # issue url or task text
    status: str = "queued"         # queued | running | done | failed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    events: list = field(default_factory=list)
    result: dict = field(default_factory=dict)
    _cond: threading.Condition = field(default_factory=threading.Condition, repr=False)

    def emit(self, type_: str, **data):
        event = {"ts": time.time(), "type": type_, **data}
        with self._cond:
            self.events.append(event)
            self._cond.notify_all()

    def finish(self, status: str, **result):
        self.result = result
        self.emit("done" if status == "done" else "error", status=status, **result)
        with self._cond:
            self.status = status
            self._cond.notify_all()
        self.save()

    def save(self):
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "id": self.id,
            "mode": self.mode,
            "target": self.target,
            "status": self.status,
            "created_at": self.created_at,
            "result": self.result,
            "events": self.events,
        }
        (RUNS_DIR / f"{self.id}.json").write_text(json.dumps(record, indent=2, default=str))

    def to_summary(self) -> dict:
        return {
            "id": self.id,
            "mode": self.mode,
            "target": self.target[:120],
            "status": self.status,
            "created_at": self.created_at,
            "result": self.result,
        }


_runs: dict[str, Run] = {}


def get_run(run_id: str) -> Optional[Run]:
    return _runs.get(run_id)


def list_runs() -> list[dict]:
    live = [r.to_summary() for r in _runs.values()]
    seen = {r["id"] for r in live}
    if RUNS_DIR.exists():
        for f in sorted(RUNS_DIR.glob("*.json"), reverse=True):
            try:
                rec = json.loads(f.read_text())
            except Exception:
                continue
            if rec.get("id") not in seen:
                rec.pop("events", None)
                live.append(rec)
    return sorted(live, key=lambda r: r.get("created_at", ""), reverse=True)


def iter_events(run_id: str):
    """Yield events for a run until it completes. Replays history first.

    Safe for multiple concurrent consumers: each iterator keeps its own
    cursor into the event list and waits on the run's condition variable.
    """
    run = _runs.get(run_id)
    if run is None:
        yield {"type": "error", "detail": f"Unknown run: {run_id}"}
        return
    cursor = 0
    while True:
        with run._cond:
            while cursor >= len(run.events) and run.status not in ("done", "failed"):
                run._cond.wait(timeout=15)
            pending = list(run.events[cursor:])
            finished = run.status in ("done", "failed")
        for event in pending:
            yield event
        cursor += len(pending)
        if finished and cursor >= len(run.events):
            return


# ---------------------------------------------------------------------------
# Run execution
# ---------------------------------------------------------------------------

_NODE_LABELS = {
    "plan": "Planning fix",
    "decompose": "Decomposing into sub-tasks",
    "explore": "Exploring codebase (hybrid retrieval)",
    "code": "Writing code",
    "test": "Running tests",
    "debug": "Debugging failures",
    "review": "Self-reviewing changes",
    "open_pr": "Opening pull request",
}


def _initial_state(issue_url, issue_number, title, body, owner, repo_name, repo_path, no_pr) -> dict:
    return {
        "issue_url": issue_url,
        "issue_number": issue_number,
        "issue_title": title,
        "issue_body": body,
        "repo_owner": owner,
        "repo_name": repo_name,
        "repo_path": repo_path,
        "no_pr": no_pr,
        "action_plan": [],
        "files_to_edit": [],
        "messages": [],
        "code_changes": [],
        "test_output": None,
        "test_passed": False,
        "retry_count": 0,
        "branch_name": None,
        "pr_url": None,
        "error": None,
        "total_tokens": 0,
    }


def _execute(run: Run, state: dict, dry_run: bool):
    from devrag.tools.rag_search import ensure_repo_indexed

    usage_before = llm_usage.stats()
    run.status = "running"
    started = time.time()

    try:
        run.emit("status", detail="Indexing repository (shared hybrid index)")
        key = ensure_repo_indexed(state["repo_path"])
        run.emit("status", detail=f"Index ready: {key}" if key else "Index unavailable — falling back to grep")

        if dry_run:
            from devrag.agent.planner import planner_node

            update = planner_node(state)
            run.emit("node", node="plan", label=_NODE_LABELS["plan"],
                     action_plan=update.get("action_plan"),
                     files_to_edit=update.get("files_to_edit"),
                     test_command=update.get("test_command"))
            run.finish("done", dry_run=True, action_plan=update.get("action_plan"),
                       files_to_edit=update.get("files_to_edit"))
            return

        from devrag.agent.graph import app as agent_graph

        final_state = dict(state)
        for chunk in agent_graph.stream(state, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                detail: dict = {"node": node_name, "label": _NODE_LABELS.get(node_name, node_name)}
                if isinstance(node_output, dict):
                    final_state.update(node_output)
                    if node_output.get("action_plan"):
                        detail["action_plan"] = node_output["action_plan"]
                    if node_output.get("code_changes") is not None:
                        detail["files_changed"] = sorted({c["file"] for c in node_output.get("code_changes", [])})
                    if "test_passed" in node_output and node_output.get("test_output") is not None:
                        detail["test_passed"] = node_output["test_passed"]
                        detail["test_output"] = (node_output.get("test_output") or "")[-1500:]
                    if node_output.get("pr_url"):
                        detail["pr_url"] = node_output["pr_url"]
                    if node_output.get("total_tokens"):
                        detail["total_tokens"] = node_output["total_tokens"]
                run.emit("node", **detail)

        if final_state.get("code_changes"):
            run.emit("status", detail="Re-indexing repository so chat reflects the changes")
            try:
                from devrag.rag.service import get_pipeline

                get_pipeline().reingest_directory(str(state["repo_path"]))
            except Exception as e:
                logger.warning(f"Re-index after run failed for {state['repo_path']}: {e}")

        usage_after = llm_usage.stats()
        elapsed = round(time.time() - started, 1)
        run.finish(
            "done",
            test_passed=final_state.get("test_passed", False),
            files_changed=sorted({c["file"] for c in final_state.get("code_changes", [])}),
            pr_url=final_state.get("pr_url"),
            error=final_state.get("error"),
            retries=final_state.get("retry_count", 0),
            total_tokens=final_state.get("total_tokens", 0),
            cost_usd=round(usage_after["cost_usd"] - usage_before["cost_usd"], 4),
            elapsed_seconds=elapsed,
        )
    except Exception as e:
        logger.exception(f"Run {run.id} failed")
        run.finish("failed", error=str(e))


def _check_repo_permission(owner: str, pr_mode: bool) -> None:
    """Refuse PR-mode runs against repos the token user does not own unless
    ALLOW_THIRD_PARTY_REPOS is set. Unsolicited automated pull requests to
    third-party repositories violate GitHub's Acceptable Use Policies."""
    from devrag import config

    if not pr_mode or config.ALLOW_THIRD_PARTY_REPOS:
        return
    try:
        from devrag.tools.github_client import get_authenticated_login

        login = get_authenticated_login()
    except Exception:
        return  # cannot determine identity; clone/PR steps will surface auth errors
    if owner.lower() != login.lower():
        raise PermissionError(
            f"PR mode against a repository you do not own ({owner} != {login}). "
            f"Only open automated pull requests on repos you own or have contributor "
            f"consent for. Use dry_run/no_pr, or set ALLOW_THIRD_PARTY_REPOS=true in .env "
            f"if you have permission to contribute."
        )


def start_issue_run(issue_url: str, dry_run: bool = False, no_pr: bool = False) -> Run:
    """Fix a GitHub issue end to end."""
    from devrag.tools.github_client import clone_repo, fetch_issue, parse_issue_url

    run = Run(id=uuid.uuid4().hex[:12], mode="issue", target=issue_url)
    _runs[run.id] = run

    def worker():
        try:
            run.emit("status", detail="Fetching issue")
            owner, repo_name, issue_num = parse_issue_url(issue_url)
            _check_repo_permission(owner, pr_mode=not (dry_run or no_pr))
            issue = fetch_issue(owner, repo_name, issue_num)
            run.emit("status", detail=f"{owner}/{repo_name}#{issue_num}: {issue['title']}")

            run.emit("status", detail="Cloning repository")
            repo_path = clone_repo(owner, repo_name, use_fork=not (dry_run or no_pr))

            state = _initial_state(issue_url, issue_num, issue["title"], issue["body"],
                                   owner, repo_name, repo_path, no_pr)
            _execute(run, state, dry_run)
        except Exception as e:
            logger.exception(f"Run {run.id} setup failed")
            run.finish("failed", error=str(e))

    threading.Thread(target=worker, daemon=True, name=f"devrag-run-{run.id}").start()
    return run


def start_task_run(repo_path: str, task: str, dry_run: bool = False) -> Run:
    """Run the agent on a free-text task against a local repo (no PR)."""
    run = Run(id=uuid.uuid4().hex[:12], mode="task", target=task)
    _runs[run.id] = run

    title = task.strip().splitlines()[0][:100]
    state = _initial_state(
        issue_url="", issue_number=0, title=title, body=task,
        owner="", repo_name=Path(repo_path).name, repo_path=str(repo_path), no_pr=True,
    )

    threading.Thread(
        target=_execute, args=(run, state, dry_run), daemon=True, name=f"devrag-run-{run.id}"
    ).start()
    return run
