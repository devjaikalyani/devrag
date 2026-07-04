"""
filesystem.py — LangChain tools for interacting with the local codebase.

Safety:
  - All paths resolved inside repo_root (no traversal)
  - run_bash has hard timeout + blocked dangerous patterns
  - All outputs capped at TOOL_OUTPUT_LIMIT chars
"""
from __future__ import annotations
import os
import pathlib
import subprocess
import re
from langchain_core.tools import tool
from devrag import config

_BLOCKED_PATTERNS = ["rm -rf /", "rm -rf ~", ":(){:|:&};:", "mkfs", "> /dev/sda"]


def _safe_path(repo_root: str, rel_path: str) -> pathlib.Path:
    root = pathlib.Path(repo_root).resolve()
    target = (root / rel_path).resolve()
    if not str(target).startswith(str(root)):
        raise PermissionError(f"Path traversal blocked: {rel_path}")
    return target


def _trim(text: str) -> str:
    lim = config.TOOL_OUTPUT_LIMIT
    if len(text) <= lim:
        return text
    half = lim // 2
    return text[:half] + f"\n\n...[TRIMMED {len(text)-lim} chars]...\n\n" + text[-half:]


@tool
def read_file(repo_root: str, path: str) -> str:
    """Read the full contents of a file inside the repository.
    Args:
        repo_root: Absolute path to the cloned repo.
        path: Path relative to repo_root (e.g. 'src/utils.py').
    Returns: File contents string, trimmed to config.TOOL_OUTPUT_LIMIT chars if large.
             If trimmed, a WARNING header is prepended explaining the file is larger than shown.
             For large files, always use str_replace_in_file (never write_file).
    """
    try:
        raw = _safe_path(repo_root, path).read_text(encoding="utf-8", errors="replace")
        total_chars = len(raw)
        lim = config.TOOL_OUTPUT_LIMIT
        if total_chars > lim:
            half = lim // 2
            trimmed = raw[:half] + f"\n\n...[TRIMMED — file is {total_chars} chars total, showing first+last {half}]...\n\n" + raw[-half:]
            return (
                f"warning  WARNING: This file is {total_chars} chars. Only a portion is shown below.\n"
                f"    DO NOT use write_file on this file — you will lose the middle section.\n"
                f"    Use str_replace_in_file for ALL edits to this file.\n\n"
                + trimmed
            )
        return raw
    except FileNotFoundError:
        return f"ERROR: File not found: {path}"
    except Exception as e:
        return f"ERROR reading {path}: {e}"


@tool
def write_file(repo_root: str, path: str, content: str) -> str:
    """Write (or overwrite) a file inside the repository. Creates parent dirs.
    SAFETY: Blocked if the existing file is larger than FILE_SIZE_LIMIT_FOR_WRITE
    to prevent accidentally overwriting large files with truncated content.
    Use str_replace_in_file for targeted edits on large files.
    Args:
        repo_root: Absolute path to the cloned repo.
        path: Relative path of the file to write.
        content: Full file content.
    Returns: Success or error message.
    """
    try:
        target = _safe_path(repo_root, path)
        # Guard: if the file already exists and is large, refuse write_file
        if target.exists():
            existing_size = len(target.read_text(encoding="utf-8", errors="replace"))
            limit = config.FILE_SIZE_LIMIT_FOR_WRITE
            if existing_size > limit:
                return (
                    f"ERROR: write_file refused — {path} is {existing_size} chars "
                    f"(limit {limit}). Use str_replace_in_file for targeted edits on large files. "
                    f"This prevents accidentally overwriting a large file with truncated content."
                )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} chars to {path}"
    except Exception as e:
        return f"ERROR writing {path}: {e}"


@tool
def str_replace_in_file(repo_root: str, path: str, old_str: str, new_str: str) -> str:
    """Replace an EXACT string in a file. old_str must appear exactly once.
    Safer than full rewrites for small targeted changes.
    Args:
        repo_root: Absolute path to the cloned repo.
        path: Relative path of the file to edit.
        old_str: Exact string to find (including whitespace/newlines).
        new_str: Replacement string.
    Returns: Success or error message.
    """
    try:
        target = _safe_path(repo_root, path)
        content = target.read_text(encoding="utf-8")
        count = content.count(old_str)
        if count == 0:
            return f"ERROR: old_str not found in {path}. Check exact whitespace."
        if count > 1:
            return f"ERROR: old_str found {count} times in {path}. Make it more specific."
        target.write_text(content.replace(old_str, new_str, 1), encoding="utf-8")
        return f"Replaced successfully in {path}"
    except Exception as e:
        return f"ERROR in str_replace for {path}: {e}"


@tool
def list_directory(repo_root: str, path: str = ".", max_depth: int = 3) -> str:
    """List files and directories up to max_depth levels deep. Skips .git, __pycache__, node_modules.
    Args:
        repo_root: Absolute path to the cloned repo.
        path: Relative path to start listing from (default: root).
        max_depth: Recursion depth (default 3).
    Returns: Tree-like string of directory structure.
    """
    SKIP = {".git", "__pycache__", ".venv", "venv", "node_modules",
            ".mypy_cache", ".pytest_cache", "dist", "build", ".eggs"}
    try:
        start = _safe_path(repo_root, path)
        lines: list[str] = []

        def walk(p: pathlib.Path, depth: int, prefix: str) -> None:
            if depth > max_depth:
                return
            try:
                entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
            except PermissionError:
                return
            for i, entry in enumerate(entries):
                if entry.name in SKIP:
                    continue
                connector = "└── " if i == len(entries) - 1 else "├── "
                lines.append(f"{prefix}{connector}{entry.name}")
                if entry.is_dir():
                    ext = "    " if i == len(entries) - 1 else "│   "
                    walk(entry, depth + 1, prefix + ext)

        lines.append(str(pathlib.Path(path)))
        walk(start, 1, "")
        return _trim("\n".join(lines))
    except Exception as e:
        return f"ERROR listing {path}: {e}"


@tool
def search_code(repo_root: str, pattern: str, file_pattern: str = "") -> str:
    """Search for a regex pattern across the codebase using grep with 2 lines context.
    Args:
        repo_root: Absolute path to the cloned repo.
        pattern: Regex pattern (e.g. 'def process_payment').
        file_pattern: Optional glob to limit files (e.g. '*.py').
    Returns: Matching lines with context, trimmed to 4000 chars.
    """
    try:
        cmd = ["grep", "-rn", "--context=2", "--color=never", pattern, "."]
        if file_pattern:
            cmd += ["--include", file_pattern]
        result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, timeout=30)
        return _trim(result.stdout or "(no matches found)")
    except subprocess.TimeoutExpired:
        return "ERROR: search timed out after 30s"
    except Exception as e:
        return f"ERROR searching: {e}"


@tool
def run_bash(repo_root: str, command: str) -> str:
    """Execute a bash command inside the repository directory.
    Use for: running tests, linters, git diff, checking imports.
    BLOCKED: rm -rf /, mkfs, fork bombs.
    Args:
        repo_root: Absolute path to run the command in.
        command: Shell command string.
    Returns: stdout + stderr output, trimmed to 4000 chars.
    """
    for blocked in _BLOCKED_PATTERNS:
        if blocked in command:
            return f"ERROR: Blocked dangerous command: '{blocked}'"
    try:
        result = subprocess.run(
            command, shell=True, cwd=repo_root,
            capture_output=True, text=True,
            timeout=config.SANDBOX_TIMEOUT,
        )
        return _trim(f"[exit code: {result.returncode}]\n{result.stdout}{result.stderr}")
    except subprocess.TimeoutExpired:
        return f"ERROR: Command timed out after {config.SANDBOX_TIMEOUT}s"
    except Exception as e:
        return f"ERROR running command: {e}"