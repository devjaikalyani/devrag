"""
test_single.py — Local integration test with 3 scenarios.

Scenario 1 (BASIC):      simple one-line bug in src/calculator.py
Scenario 2 (LARGE FILE): bug in source + large pyproject.toml present
                          — verifies write_file guard doesn't destroy config
Scenario 3 (SOURCE vs TEST): bug in source, test file present
                          — verifies DevRAG edits source, NOT the test file

Usage:
  python scripts/test_single.py              # runs all 3
  python scripts/test_single.py --scenario 1 # run one scenario
"""
from __future__ import annotations

import argparse
import difflib
import sys
import tempfile
import pathlib
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1: basic one-line fix
# ─────────────────────────────────────────────────────────────────────────────

S1_FILES = {
    "src/__init__.py": "",
    "src/calculator.py": '''\
def safe_divide(a: float, b: float) -> float:
    """Divide a by b. Should handle division by zero gracefully."""
    return a / b   # BUG: raises ZeroDivisionError when b == 0
''',
    "tests/__init__.py": "",
    "tests/test_calculator.py": '''\
import pytest
from src.calculator import safe_divide


def test_normal_division():
    assert safe_divide(10, 2) == 5.0


def test_divide_by_zero_returns_none():
    result = safe_divide(10, 0)
    assert result is None, f"Expected None, got {result}"


def test_divide_by_zero_does_not_raise():
    try:
        result = safe_divide(5, 0)
    except ZeroDivisionError:
        pytest.fail("safe_divide should not raise ZeroDivisionError")
''',
    "pytest.ini": "[pytest]\ntestpaths = tests\n",
}

S1_ISSUE = {
    "number": 1,
    "title":  "safe_divide crashes with ZeroDivisionError when b=0",
    "body": (
        "## Bug Report\n\n"
        "Calling `safe_divide(10, 0)` raises `ZeroDivisionError` instead of returning `None`.\n\n"
        "**Expected:** returns `None`\n"
        "**Actual:** raises `ZeroDivisionError`"
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2: source bug + large config (tests the write_file guard)
# ─────────────────────────────────────────────────────────────────────────────

_BIG_PYPROJECT = """\
[build-system]
requires = ["setuptools>=77", "setuptools-scm[toml]>=6.2.3"]
build-backend = "setuptools.build_meta"

[project]
name = "mylib"
description = "A sample library"
readme = "README.rst"
license = "MIT"
requires-python = ">=3.10"
dependencies = [
    "colorama>=0.4; sys_platform=='win32'",
    "packaging>=22",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"

[tool.ruff]
target-version = "py310"
line-length = 88
src = ["src"]

[tool.ruff.lint]
select = ["B", "E", "F", "I", "UP", "W"]
ignore = [
    "B004", "B007", "B009", "B010", "B011", "B028",
    "E501", "E741",
    "UP006", "UP007",
    "W503",
]

[tool.mypy]
python_version = "3.10"
strict = true
ignore_missing_imports = true
show_error_codes = true
warn_return_any = true
warn_unreachable = true

[tool.coverage.report]
skip_covered = true
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "assert False",
    "if TYPE_CHECKING:",
]

[tool.coverage.run]
branch = true
parallel = true
source = ["src/"]
""" + "\n".join(f"# config padding line {i:04d} = {'x' * 60}" for i in range(120))

S2_FILES = {
    "src/__init__.py": "",
    "src/strings.py": '''\
def truncate(text: str, max_len: int) -> str:
    """Return text truncated to max_len chars. Adds '...' if truncated."""
    if len(text) <= max_len:
        return text
    return text[:max_len]   # BUG: missing "..." suffix
''',
    "tests/__init__.py": "",
    "tests/test_strings.py": '''\
from src.strings import truncate


def test_no_truncation_needed():
    assert truncate("hello", 10) == "hello"


def test_truncation_adds_ellipsis():
    result = truncate("hello world", 5)
    assert result == "hello...", f"Expected 'hello...', got {repr(result)}"


def test_exact_length():
    assert truncate("hello", 5) == "hello"
''',
    "pyproject.toml": _BIG_PYPROJECT,
}

S2_ISSUE = {
    "number": 2,
    "title":  "truncate() doesn't add '...' when text is cut",
    "body": (
        "## Bug Report\n\n"
        "`truncate('hello world', 5)` returns `'hello'` instead of `'hello...'`.\n\n"
        "The bug is in `src/strings.py` — the `truncate` function is missing the `'...'` suffix.\n\n"
        "**Expected:** `'hello...'`\n"
        "**Actual:** `'hello'`"
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 3: source bug with distracting test file (source-vs-test separation)
# ─────────────────────────────────────────────────────────────────────────────

S3_FILES = {
    "src/__init__.py": "",
    "src/validators.py": '''\
import re

EMAIL_REGEX = r"[^@]+"   # BUG: too permissive, doesn't validate domain part

def is_valid_email(email: str) -> bool:
    """Return True if email is a valid email address."""
    return bool(re.match(EMAIL_REGEX, email))
''',
    "tests/__init__.py": "",
    "tests/test_validators.py": '''\
from src.validators import is_valid_email


def test_valid_email():
    assert is_valid_email("user@example.com") is True


def test_invalid_no_at_sign():
    assert is_valid_email("notanemail") is False


def test_invalid_no_domain():
    assert is_valid_email("user@") is False


def test_valid_subdomain():
    assert is_valid_email("user@mail.example.com") is True
''',
    "pytest.ini": "[pytest]\ntestpaths = tests\n",
}

S3_ISSUE = {
    "number": 3,
    "title":  "is_valid_email accepts strings without a proper domain",
    "body": (
        "## Bug Report\n\n"
        "`is_valid_email('user@')` returns `True` — it should return `False`.\n\n"
        "The fix is in `src/validators.py`. The `EMAIL_REGEX` constant is too permissive.\n"
        "Use a proper regex like `r'^[^@]+@[^@]+\\.[^@]+$'` instead.\n\n"
        "**Do NOT edit the test file.** It already has the correct assertions.\n\n"
        "**Expected:** `is_valid_email('user@')` → `False`\n"
        "**Actual:** `is_valid_email('user@')` → `True`"
    ),
}


SCENARIOS = {
    1: ("BASIC — simple one-line fix",              S1_FILES, S1_ISSUE),
    2: ("LARGE FILE — config must survive intact",  S2_FILES, S2_ISSUE),
    3: ("SOURCE vs TEST — must not edit test file", S3_FILES, S3_ISSUE),
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_repo(tmp_path: pathlib.Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


def snapshot(repo: pathlib.Path) -> dict[str, str]:
    snap: dict[str, str] = {}
    for f in sorted(repo.rglob("*")):
        if any(p in str(f) for p in ["__pycache__", ".venv", ".git"]):
            continue
        if f.is_file():
            snap[str(f.relative_to(repo))] = f.read_text(errors="replace")
    return snap


def show_diff(before: dict[str, str], after: dict[str, str]) -> None:
    console.print(f"\n[bold yellow]{'─'*70}[/bold yellow]")
    console.print("[bold yellow]  CHANGES MADE BY DEVRAG[/bold yellow]")
    console.print(f"[bold yellow]{'─'*70}[/bold yellow]")
    changed = False

    for path in sorted(set(before) | set(after)):
        b = before.get(path, "")
        a = after.get(path, "")
        if b == a:
            continue
        changed = True

        b_size, a_size = len(b), len(a)
        shrink = ""
        if b_size > 0 and a_size < b_size * 0.5:
            shrink = f"  [bold red]warning  SHRUNK {b_size}→{a_size} chars — data loss![/bold red]"

        console.print(f"\n[bold magenta]  MODIFIED: {path}[/bold magenta]{shrink}")

        diff = list(difflib.unified_diff(
            b.splitlines(keepends=True), a.splitlines(keepends=True),
            fromfile=f"BEFORE  {path}", tofile=f"AFTER   {path}", n=3,
        ))
        coloured = Text()
        for line in diff:
            if not line.endswith("\n"):
                line += "\n"
            if line.startswith(("+++", "---")):
                coloured.append(line, style="bold white")
            elif line.startswith("@@"):
                coloured.append(line, style="bold cyan")
            elif line.startswith("+"):
                coloured.append(line, style="bold green")
            elif line.startswith("-"):
                coloured.append(line, style="bold red")
            else:
                coloured.append(line, style="dim")
        console.print(coloured)

    if not changed:
        console.print("\n  [yellow]No changes detected.[/yellow]")


def show_summary(passed: bool, output: str, retries: int, elapsed: float, tokens: int,
                 cost: float = 0.0) -> None:
    console.print(f"\n[bold]{'─'*70}[/bold]")
    console.print("[bold]  RUN SUMMARY[/bold]")
    console.print(f"[bold]{'─'*70}[/bold]")
    t = Table(box=box.SIMPLE, show_header=False)
    t.add_column("Key", style="cyan", min_width=20)
    t.add_column("Value", style="white")
    t.add_row("Result",  "[bold green]ok PASSED[/bold green]" if passed else "[bold red]FAIL FAILED[/bold red]")
    t.add_row("Retries", str(retries))
    t.add_row("Time",    f"{elapsed:.1f}s")
    t.add_row("Tokens",  f"{tokens:,}")
    t.add_row("Cost",    f"${cost:.4f}")
    console.print(t)
    if not passed:
        lines = [l for l in output.splitlines() if l.strip()][-25:]
        console.print("\n[red]  Test output:[/red]")
        console.print("[dim]" + "\n".join(f"    {l}" for l in lines) + "[/dim]")


# ─────────────────────────────────────────────────────────────────────────────
# Scenario-specific validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_s2(before: dict, after: dict) -> list[str]:
    issues = []
    b, a = before.get("pyproject.toml", ""), after.get("pyproject.toml", "")
    if b != a:
        issues.append(f"pyproject.toml was modified! ({len(b)} → {len(a)} chars) — large-file guard FAILED")
    else:
        console.print("[bold green]  ok pyproject.toml untouched — large-file guard worked![/bold green]")
    return issues


def validate_s3(before: dict, after: dict) -> list[str]:
    issues = []
    tf = "tests/test_validators.py"
    sf = "src/validators.py"
    if before.get(tf) != after.get(tf):
        issues.append(f"{tf} was modified — DevRAG must NOT edit test files!")
    else:
        console.print("[bold green]  ok test file untouched — source-vs-test separation worked![/bold green]")
    if before.get(sf) == after.get(sf):
        issues.append(f"{sf} was NOT modified — the fix must go in the source file!")
    else:
        console.print("[bold green]  ok source file was fixed![/bold green]")
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Run one scenario
# ─────────────────────────────────────────────────────────────────────────────

def run_scenario(n: int) -> bool:
    label, files, issue = SCENARIOS[n]
    console.print(Panel.fit(
        f"[bold green]DevRAG[/bold green] — Scenario {n}: {label}",
        border_style="green",
    ))

    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"devrag_s{n}_"))
    create_repo(tmp, files)
    console.print(f"[bold]Repo:[/bold] {tmp}\n")

    snap_before = snapshot(tmp)

    initial_state = {
        "issue_url":    f"https://github.com/test/repo/issues/{issue['number']}",
        "issue_number": issue["number"],
        "issue_title":  issue["title"],
        "issue_body":   issue["body"],
        "repo_owner":   "test",
        "repo_name":    "repo",
        "repo_path":    str(tmp),
        "branch_name":  "",
        "action_plan":  [],
        "files_to_edit": [],
        "repo_map":     "",
        "test_command": "",
        "messages":     [],
        "code_changes": [],
        "test_output":  "",
        "test_passed":  False,
        "retry_count":  0,
        "max_retries":  5,
        "pr_url":       None,
        "pr_number":    None,
        "error":        None,
        "total_tokens": 0,
        "no_pr":        True,
    }

    from devrag.agent.graph import app as agent_app
    from devrag.llm.client import usage as llm_usage

    cost_before = llm_usage.stats()["cost_usd"]
    start = time.time()
    final: dict = {}

    # no_pr=True routes review -> END, so no GitHub credentials are needed
    for chunk in agent_app.stream(initial_state, stream_mode="updates"):
        for _, out in chunk.items():
            if isinstance(out, dict):
                final.update(out)

    elapsed = time.time() - start
    cost = llm_usage.stats()["cost_usd"] - cost_before
    snap_after = snapshot(tmp)

    show_diff(snap_before, snap_after)

    extra: list[str] = []
    if n == 2:
        extra = validate_s2(snap_before, snap_after)
    elif n == 3:
        extra = validate_s3(snap_before, snap_after)

    for w in extra:
        console.print(f"[bold red]   {w}[/bold red]")

    show_summary(
        passed=final.get("test_passed", False),
        output=final.get("test_output", ""),
        retries=final.get("retry_count", 0),
        elapsed=elapsed,
        tokens=final.get("total_tokens", 0),
        cost=cost,
    )

    success = final.get("test_passed", False) and not extra

    if success:
        console.print(f"\n[bold green]ok Scenario {n} passed in {elapsed:.1f}s![/bold green]")
    else:
        console.print(f"\n[bold red]FAIL Scenario {n} failed.[/bold red]")

    return success


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="DevRAG local integration tests")
    parser.add_argument("--scenario", type=int, choices=[1, 2, 3],
                        help="Run only this scenario (default: all 3)")
    args = parser.parse_args()

    to_run = [args.scenario] if args.scenario else [1, 2, 3]
    results: dict[int, bool] = {}

    for s in to_run:
        console.print(f"\n{'═'*70}")
        results[s] = run_scenario(s)
        console.print(f"{'═'*70}\n")

    if len(to_run) > 1:
        console.print(Panel.fit("[bold]FINAL RESULTS[/bold]", border_style="cyan"))
        t = Table(box=box.SIMPLE, show_header=True)
        t.add_column("Scenario", style="cyan")
        t.add_column("Description", style="white")
        t.add_column("Result", style="white")
        for s, passed in results.items():
            t.add_row(str(s), SCENARIOS[s][0],
                      "[bold green]ok PASS[/bold green]" if passed else "[bold red]FAIL FAIL[/bold red]")
        console.print(t)
        p = sum(results.values())
        total = len(results)
        color = "green" if p == total else "yellow" if p > 0 else "red"
        console.print(f"\n[bold {color}]{p}/{total} scenarios passed[/bold {color}]")

    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()