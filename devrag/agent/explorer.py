"""
explorer.py — Builds the code context for the coder. Zero LLM calls.

Three sources of context, in order of precision:
  1. Files the planner flagged (read directly)
  2. Hybrid semantic retrieval over the shared repo index (the DevRAG merge:
     the same CodeBERT+FAISS+BM25 index that powers chat grounds the agent)
  3. Grep fallback on keywords from the issue title

Key rule: test files are read for CONTEXT only (so the coder knows what to
satisfy). They are never put in files_to_edit — the coder must fix
source/implementation files.
"""
from __future__ import annotations
import re
from .state import AgentState
from devrag.tools.filesystem import read_file, list_directory, search_code
from devrag.tools.rag_search import retrieve_chunks, format_chunks
from rich.console import Console

console = Console()

_TEST_PATTERNS = re.compile(r'(^|/)test[s]?[_/]|_test\.py$|/test_')


def _is_test_file(path: str) -> bool:
    """Return True if path looks like a test file."""
    return bool(_TEST_PATTERNS.search(path)) or path.startswith("test_") or "/test_" in path


def explorer_node(state: AgentState) -> dict:
    console.print("[bold cyan]Exploring codebase...[/bold cyan]")

    repo_path = state["repo_path"]
    source_files: dict[str, str] = {}   # source implementation files to edit
    test_files:   dict[str, str] = {}   # test files for context only

    # 1. Read planner-suggested files (filter out fake/synthetic names)
    for rel_path in state.get("files_to_edit", []):
        if not rel_path or not re.search(r'\.\w+$', rel_path):
            continue
        content = read_file.invoke({"repo_root": repo_path, "path": rel_path})
        if not content.startswith("ERROR"):
            if _is_test_file(rel_path):
                test_files[rel_path] = content
                console.print(f"[dim]  read test (context only): {rel_path} ({len(content)} chars)[/dim]")
            else:
                source_files[rel_path] = content
                console.print(f"[dim]  read source: {rel_path} ({len(content)} chars)[/dim]")

    # 2. Hybrid semantic retrieval over the shared index (if built for this repo).
    #    Queries: issue title + the first plan steps.
    rag_chunks: list[dict] = []
    seen_chunk_keys: set[tuple] = set()
    queries = [state.get("issue_title", "")] + list(state.get("action_plan", []))[:3]
    for q in [q for q in queries if q and len(q) > 8]:
        for c in retrieve_chunks(q, top_k=4):
            key = (c["source"], c["start_line"])
            if key not in seen_chunk_keys:
                seen_chunk_keys.add(key)
                rag_chunks.append(c)
    rag_chunks = rag_chunks[:8]
    if rag_chunks:
        console.print(f"[dim]  retrieved {len(rag_chunks)} relevant chunk(s) from the repo index[/dim]")

    # 2b. If the planner gave no usable source files, promote retrieved files
    if not source_files:
        for c in rag_chunks:
            rel = c["source"]
            if _is_test_file(rel) or rel in source_files:
                continue
            content = read_file.invoke({"repo_root": repo_path, "path": rel})
            if not content.startswith("ERROR"):
                source_files[rel] = content
                console.print(f"[dim]  promoted from retrieval: {rel}[/dim]")
            if len(source_files) >= 3:
                break

    # 3. Grep fallback: function names from issue title in source files only
    if not source_files:
        words = [w for w in re.split(r'\W+', state.get("issue_title", "")) if len(w) > 3]
        query = words[0] if words else "def "
        hits  = search_code.invoke({"repo_root": repo_path, "pattern": query, "file_pattern": "*.py"})
        found = list(dict.fromkeys(m.group(1) for line in hits.splitlines()
                                   if (m := re.match(r'^([^:\s][^:]+\.py):', line))))
        for p in found[:5]:
            if _is_test_file(p):
                continue   # skip test files in the fallback search
            content = read_file.invoke({"repo_root": repo_path, "path": p})
            if not content.startswith("ERROR"):
                source_files[p] = content
                console.print(f"[dim]  found source: {p}[/dim]")

    # 4. Read relevant test files for context (coder needs to know what tests expect)
    test_hits = search_code.invoke({"repo_root": repo_path, "pattern": "def test_", "file_pattern": "*.py"})
    test_paths = list(dict.fromkeys(m.group(1) for line in test_hits.splitlines()
                                    if (m := re.match(r'^([^:\s][^:]+\.py):', line))))
    for tp in test_paths[:2]:
        if tp not in test_files and tp not in source_files:
            content = read_file.invoke({"repo_root": repo_path, "path": tp})
            if not content.startswith("ERROR"):
                test_files[tp] = content
                console.print(f"[dim]  read test (context only): {tp}[/dim]")

    console.print(
        f"[dim]  Explorer done — "
        f"{len(source_files)} source file(s) to edit, "
        f"{len(test_files)} test file(s) for context, "
        f"{len(rag_chunks)} retrieved chunk(s), 0 LLM calls[/dim]"
    )

    # Detect repos with no source code (like GitHub Skills tutorials)
    no_source_code = len(source_files) == 0 and len(test_files) == 0
    if no_source_code:
        dir_listing = list_directory.invoke({"repo_root": repo_path, "path": "."})
        has_only_docs = all(
            any(ext in line for ext in ['.md', '.txt', '.yml', '.yaml', '.json', 'LICENSE', 'README'])
            for line in dir_listing.splitlines() if line.strip() and not line.startswith('.')
        )
        if has_only_docs:
            console.print("[yellow]  This appears to be a documentation/tutorial repo with no source code[/yellow]")

    # Build context string: source files first, then retrieved chunks, then tests
    source_parts = [
        f"### SOURCE FILE TO FIX: {path}\n```python\n{content}\n```"
        for path, content in source_files.items()
    ]
    # Skip retrieved chunks that duplicate files already included in full
    fresh_chunks = [c for c in rag_chunks if c["source"] not in source_files and c["source"] not in test_files]
    rag_part = [format_chunks(fresh_chunks)] if fresh_chunks else []
    test_parts = [
        f"### TEST FILE (context only — do NOT edit): {path}\n```python\n{content}\n```"
        for path, content in test_files.items()
    ]
    file_context = "\n\n".join(source_parts + rag_part + test_parts)

    return {
        "messages":      [{"role": "user", "content": file_context}],
        # Only source files go in files_to_edit — test files are excluded
        "files_to_edit": list(source_files.keys()),
        "total_tokens":  state.get("total_tokens", 0),
    }
