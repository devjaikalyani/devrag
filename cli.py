"""
cli.py — DevRAG command line interface.

  devrag ingest <github-url-or-local-path>   index a repo for chat and agent runs
  devrag ask "<question>"                    ask about the active repo
  devrag solve <issue-url> [--dry-run --no-pr]
  devrag solve --repo <path> --task "<task>" [--dry-run]
  devrag serve [--port 8001]                 start the API
  devrag usage                               token/cost totals for this process
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

app = typer.Typer(name="devrag", help="Chat with any codebase, then let the agent fix it.", no_args_is_help=True)
console = Console()


@app.command()
def ingest(source: str = typer.Argument(..., help="GitHub URL or local directory path"),
           branch: str = typer.Option("main", help="Branch for GitHub ingestion")):
    """Index a repository into the shared hybrid index."""
    from devrag.rag.service import get_pipeline

    pipeline = get_pipeline()
    if source.startswith("http://") or source.startswith("https://"):
        result = pipeline.ingest_github(source, branch=branch)
    else:
        path = Path(source).expanduser().resolve()
        if not path.exists():
            console.print(f"[red]Path not found: {path}[/red]")
            raise typer.Exit(1)
        result = pipeline.ingest_directory(str(path))
    console.print(result)


@app.command()
def ask(question: str = typer.Argument(..., help="Question about the active repo"),
        repo: Optional[str] = typer.Option(None, help="Repo key to switch to first"),
        no_faithfulness: bool = typer.Option(False, "--no-faithfulness", help="Skip faithfulness scoring")):
    """Ask a question about the active (or named) repo."""
    from devrag.rag.service import get_pipeline

    pipeline = get_pipeline()
    if repo:
        result = pipeline.switch_repo(repo)
        if result.get("status") == "error":
            console.print(f"[red]{result.get('reason')}[/red]")
            raise typer.Exit(1)
    if pipeline.retriever is None:
        console.print("[red]No repo selected. Run devrag ingest first.[/red]")
        raise typer.Exit(1)

    response = pipeline.query(question, check_faithfulness=not no_faithfulness)
    console.print(Markdown(response.answer))
    console.print()
    for r in response.sources[:5]:
        console.print(f"[dim]  source: {r.chunk.source}:{r.chunk.start_line}-{r.chunk.end_line} "
                      f"(score {r.rerank_score:.3f})[/dim]")
    if response.faithfulness:
        verdict = "faithful" if response.faithfulness.is_faithful else "NOT faithful"
        console.print(f"[dim]  faithfulness: {response.faithfulness.score:.2f} ({verdict})[/dim]")


@app.command()
def solve(issue_url: Optional[str] = typer.Argument(None, help="GitHub issue URL"),
          repo: Optional[str] = typer.Option(None, "--repo", help="Local repo path (task mode)"),
          task: Optional[str] = typer.Option(None, "--task", help="Free-text task (task mode)"),
          dry_run: bool = typer.Option(False, "--dry-run", help="Plan only, change nothing"),
          no_pr: bool = typer.Option(False, "--no-pr", help="Fix and test but do not open a PR")):
    """Run the autonomous agent on a GitHub issue or a local task."""
    from devrag import config
    from devrag.agent import runner

    config.cfg.validate()

    if issue_url:
        run = runner.start_issue_run(issue_url, dry_run=dry_run, no_pr=no_pr)
    elif repo and task:
        repo_path = Path(repo).expanduser().resolve()
        if not repo_path.exists():
            console.print(f"[red]Path not found: {repo_path}[/red]")
            raise typer.Exit(1)
        run = runner.start_task_run(str(repo_path), task, dry_run=dry_run)
    else:
        console.print("[red]Provide an issue URL, or both --repo and --task.[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Run {run.id} started[/bold] ({run.mode} mode)\n")
    for event in runner.iter_events(run.id):
        etype = event.get("type")
        if etype == "status":
            console.print(f"[dim]{event.get('detail')}[/dim]")
        elif etype == "node":
            console.print(f"[cyan]{event.get('label', event.get('node'))}[/cyan]")
            for step in event.get("action_plan") or []:
                console.print(f"  [dim]- {step}[/dim]")
            if event.get("files_changed"):
                console.print(f"  [dim]files: {', '.join(event['files_changed'])}[/dim]")
            if event.get("test_passed") is not None and "test_output" in event:
                colour = "green" if event["test_passed"] else "yellow"
                console.print(f"  [{colour}]tests {'passed' if event['test_passed'] else 'failing'}[/{colour}]")
            if event.get("pr_url"):
                console.print(f"  [green]PR: {event['pr_url']}[/green]")
        elif etype == "done":
            console.print("\n[bold green]Run complete[/bold green]")
            if event.get("pr_url"):
                console.print(f"PR: {event['pr_url']}")
            if event.get("cost_usd") is not None:
                console.print(f"Cost: ${event['cost_usd']:.4f}  "
                              f"Elapsed: {event.get('elapsed_seconds', '?')}s")
        elif etype == "error":
            console.print(f"\n[bold red]Run failed:[/bold red] {event.get('error')}")
            raise typer.Exit(1)


@app.command()
def serve(port: int = typer.Option(None, help="Port (default from config: 8001)"),
          host: str = typer.Option(None, help="Host (default from config: 0.0.0.0)"),
          reload: bool = typer.Option(False, help="Auto-reload on code changes")):
    """Start the DevRAG API server."""
    import uvicorn

    from devrag.config import settings

    uvicorn.run("devrag.api.main:app",
                host=host or settings.api_host,
                port=port or settings.api_port,
                reload=reload)


@app.command()
def usage():
    """Show LLM token and cost totals for this process."""
    from devrag.llm.client import usage as tracker

    stats = tracker.stats()
    table = Table(title="LLM usage")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for key, value in stats.items():
        table.add_row(key, str(value))
    console.print(table)


if __name__ == "__main__":
    app()
