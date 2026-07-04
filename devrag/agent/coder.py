"""
coder.py — Writes the code fix using Mistral tool calling with caching and optimization.
Optimized for free tier rate limits with aggressive caching and token reduction.
Now with minimal conversation history to prevent message order errors.
"""
from __future__ import annotations
import json
import hashlib
import time
from functools import lru_cache
from collections import defaultdict
from pathlib import Path
from .state import AgentState
from devrag.llm.client import chat
from devrag.tools.filesystem import read_file, write_file, str_replace_in_file, search_code
from devrag.tools.rag_search import search_codebase, SEARCH_CODEBASE_TOOL
from rich.console import Console

console = Console()

# Cache for file contents to avoid repeated reads
_file_cache: dict[str, tuple[str, float]] = {}
# Cache for LLM responses
_llm_cache: dict[str, tuple[str, float, int]] = {}  # response, timestamp, tokens
# Cache TTL in seconds
CACHE_TTL = 300  # 5 minutes
# Rate limit tracking
_last_request_time = 0
MIN_REQUEST_INTERVAL = 1.0  # 1 second between requests (respects free tier)

_SYSTEM = """\
You are an expert software engineer fixing a GitHub issue.

## WORKFLOW
1. Identify which source file contains the actual bug (NOT the test file).
2. Call read_file on the implementation file to get its exact current content.
3. Call str_replace_in_file with an exact substring from the file to apply the minimal fix.
4. If str_replace_in_file returns an error ("not found"), call read_file again to refresh the content, then retry.
5. Stop once the fix is applied.

## FOR JSON/DATA FILE ADDITIONS
When adding new entries to JSON arrays (like trivia questions, config entries):
1. Read the file first to see the exact format
2. Find the LAST entry in the array
3. Use str_replace_in_file to replace the last entry with: last entry + comma + new entry
   Example: replace `"answer": "Tokyo"\n  }` with `"answer": "Tokyo"\n  },\n  {\n    "question": "New Q"\n  }`
4. Or use write_file with the complete updated JSON

## RULES
- Fix the source code, not the tests
- Minimal change only — do not refactor unrelated code
- Match existing indentation and style exactly
- For JSON: ensure valid syntax (commas, brackets)
- repo_root is provided in the task — use it exactly as given in every tool call
- IMPORTANT: You MUST make changes. Do not just read files - use str_replace_in_file or write_file."""

_TOOLS = [
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read current file content. Call before str_replace if unsure of exact text.",
        "parameters": {"type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path e.g. src/calculator.py"},
            }, "required": ["path"]},  # repo_root is injected
    }},
    {"type": "function", "function": {
        "name": "str_replace_in_file",
        "description": "Replace an EXACT string in a file. old_str must match the file content exactly.",
        "parameters": {"type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_str": {"type": "string", "description": "Exact text to replace — must appear once"},
                "new_str": {"type": "string", "description": "Replacement text"},
            }, "required": ["path", "old_str", "new_str"]},
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Overwrite entire file. ONLY for NEW files or small files (<8000 chars).",
        "parameters": {"type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string", "description": "Complete corrected file content"},
            }, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "search_code",
        "description": "Search for a pattern in the repo — use only to find a file path.",
        "parameters": {"type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "The search pattern to look for"},
                "file_pattern": {"type": "string", "description": "Optional file pattern e.g. '*.py'"},
            }, "required": ["pattern"]},
    }},
    SEARCH_CODEBASE_TOOL,
]

def _rate_limit():
    """Ensure minimum time between API requests."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()

def _get_cached_file(repo_path: str, path: str) -> str | None:
    """Get cached file content if available and not expired."""
    cache_key = f"{repo_path}:{path}"
    if cache_key in _file_cache:
        content, timestamp = _file_cache[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            return content
        else:
            del _file_cache[cache_key]
    return None

def _cache_file(repo_path: str, path: str, content: str):
    """Cache file content."""
    cache_key = f"{repo_path}:{path}"
    _file_cache[cache_key] = (content, time.time())

def _get_cache_key(messages: list, tools: list | None) -> str:
    """Generate cache key for LLM request."""
    # Only cache deterministic requests (temperature=0.0)
    msg_str = json.dumps([{k: v for k, v in m.items() if k != 'id'} for m in messages], sort_keys=True)
    tools_str = json.dumps(tools, sort_keys=True) if tools else ""
    return hashlib.md5(f"{msg_str}|{tools_str}".encode()).hexdigest()

def _get_cached_llm(cache_key: str) -> tuple[str | None, int | None]:
    """Get cached LLM response if available and not expired."""
    if cache_key in _llm_cache:
        response, timestamp, tokens = _llm_cache[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            return response, tokens
        else:
            del _llm_cache[cache_key]
    return None, None

def _cache_llm(cache_key: str, response: str, tokens: int):
    """Cache LLM response."""
    _llm_cache[cache_key] = (response, time.time(), tokens)

def _safe_search_call(args: dict, repo_path: str) -> str:
    """Safely call search_code with proper argument handling."""
    if "pattern" not in args:
        pattern = args.get("query") or args.get("search") or args.get("q")
        if pattern:
            args["pattern"] = pattern
        else:
            return f"ERROR: Missing required argument 'pattern' for search_code"
    
    args["repo_root"] = repo_path
    args["file_pattern"] = args.get("file_pattern", "")
    
    console.print(f"[dim]  search_code pattern='{args['pattern']}' file_pattern='{args['file_pattern']}'[/dim]")
    
    try:
        # Check cache first
        cache_key = f"search:{repo_path}:{args['pattern']}:{args['file_pattern']}"
        cached = _get_cached_file(repo_path, cache_key)
        if cached:
            return cached
        
        result = str(search_code.invoke(args))
        _cache_file(repo_path, cache_key, result)
        return result
    except Exception as e:
        return f"ERROR in search_code: {e}"

def _safe_tool_call(name: str, args: dict, repo_path: str) -> tuple[str, bool]:
    """Safely call a tool with error handling and repo_path injection."""
    try:
        if name == "read_file":
            if "path" not in args:
                return "ERROR: Missing required argument 'path' for read_file", False
            
            # Check cache
            cached = _get_cached_file(repo_path, args["path"])
            if cached:
                return cached, True
            
            args["repo_root"] = repo_path
            result = str(read_file.invoke(args))
            _cache_file(repo_path, args["path"], result)
            return result, "ERROR" not in result
        
        elif name == "str_replace_in_file":
            missing = [k for k in ["path", "old_str", "new_str"] if k not in args]
            if missing:
                return f"ERROR: Missing required arguments: {missing}", False
            args["repo_root"] = repo_path
            result = str(str_replace_in_file.invoke(args))
            # Invalidate cache for this file
            _file_cache.pop(f"{repo_path}:{args['path']}", None)
            return result, "ERROR" not in result
        
        elif name == "write_file":
            if "path" not in args or "content" not in args:
                return "ERROR: Missing required arguments for write_file", False
            args["repo_root"] = repo_path
            result = str(write_file.invoke(args))
            # Invalidate cache for this file
            _file_cache.pop(f"{repo_path}:{args['path']}", None)
            return result, "ERROR" not in result
        
        elif name == "search_code":
            return _safe_search_call(args, repo_path), True

        elif name == "search_codebase":
            if "query" not in args:
                return "ERROR: Missing required argument 'query' for search_codebase", False
            return search_codebase(args["query"]), True

        else:
            return f"ERROR: Unknown tool '{name}'", False
            
    except Exception as e:
        return f"ERROR calling {name}: {e}", False

def _parse_args(raw) -> dict:
    """Mistral may return arguments as dict or JSON string — handle both."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}

def _msg_to_dict(msg) -> dict:
    """Convert Mistral message object → plain dict for history."""
    d: dict = {"role": "assistant", "content": msg.content or ""}
    if getattr(msg, "tool_calls", None):
        d["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {
                 "name": tc.function.name,
                 "arguments": (tc.function.arguments if isinstance(tc.function.arguments, str)
                               else json.dumps(tc.function.arguments)),
             }}
            for tc in msg.tool_calls
        ]
    return d

def _summarize_file_context(file_context: str, max_lines: int = 30) -> str:
    """Summarize file context to reduce tokens."""
    if not file_context:
        return ""
    
    lines = file_context.split('\n')
    if len(lines) <= max_lines:
        return file_context
    
    # Return first 15 and last 15 lines
    return '\n'.join(lines[:15] + ['... (content truncated for token efficiency) ...'] + lines[-15:])

def coder_node(state: AgentState) -> dict:
    console.print("[bold cyan]Writing fix...[/bold cyan]")

    repo_path = state["repo_path"]
    plan_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(state["action_plan"]))

    # Get only the most recent file context
    file_context = ""
    for m in reversed(state.get("messages", [])):
        c = m.get("content", "")
        if m.get("role") == "user" and c.startswith("###"):
            file_context = _summarize_file_context(c)
            break

    # Start with FRESH messages - only system + current user
    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content":
            f"## Issue #{state['issue_number']}: {state['issue_title']}\n\n"
            f"{state['issue_body']}\n\n"
            f"## Action plan\n{plan_text}\n\n"
            f"## repo_root\n{repo_path}\n\n"
            f"## Source files\n{file_context}\n\n"
            f"Apply the fix now. You can use tools. Previous attempts may have failed - start fresh."
        },
    ]

    code_changes: list[dict] = []
    tokens = state.get("total_tokens", 0)
    consecutive_no_tool_calls = 0

    for iteration in range(10):
        # Apply rate limiting
        _rate_limit()

        # Cache only single-shot text responses; tool-call turns are stateful
        cache_key = _get_cache_key(messages, _TOOLS)
        cached_response, cached_tokens = _get_cached_llm(cache_key)

        if cached_response:
            console.print(f"[dim]  Using cached LLM response (iteration {iteration+1})[/dim]")
            class MockMessage:
                def __init__(self, content):
                    self.content = content
                    self.tool_calls = None
            msg = MockMessage(cached_response)
            tok = cached_tokens or 0
        else:
            msg, tok = chat(messages, tools=_TOOLS, temperature=0.0)
            if msg.content and not getattr(msg, "tool_calls", None):
                _cache_llm(cache_key, msg.content, tok)

        tokens += tok

        if not getattr(msg, "tool_calls", None):
            consecutive_no_tool_calls += 1
            messages.append({"role": "assistant", "content": msg.content or ""})
            if consecutive_no_tool_calls >= 2:
                if msg.content:
                    console.print(f"[yellow]  No tool calls (x{consecutive_no_tool_calls}) — LLM: {msg.content[:200]}[/yellow]")
                break
            # Never leave the conversation ending on an assistant turn
            messages.append({"role": "user", "content":
                             "If the fix is fully applied, reply DONE. Otherwise use the tools to finish it."})
            continue
        consecutive_no_tool_calls = 0

        # Real tool conversation: assistant tool-call turn, then one tool
        # result per call. The model keeps seeing the task, the file context,
        # and the outcome of its own edits — this is what prevents blind
        # repeated edits and provider message-order errors.
        messages.append(_msg_to_dict(msg))

        for tc in msg.tool_calls:
            name = tc.function.name
            args = _parse_args(tc.function.arguments)

            result, ok = _safe_tool_call(name, args, repo_path)

            # Minimal logging
            if name == "read_file":
                console.print(f"[dim]  {args.get('path','?')} ({len(result)} chars)[/dim]")
            elif name == "str_replace_in_file":
                console.print(f"[{'green' if ok else 'red'}]  edit {args.get('path','?')} {'ok' if ok else 'FAIL'}[/{'green' if ok else 'red'}]")
            elif name == "write_file":
                console.print(f"[{'green' if ok else 'red'}]   {args.get('path','?')} {'ok' if ok else 'FAIL'}[/{'green' if ok else 'red'}]")
            elif name == "search_code":
                console.print(f"[dim]  {args.get('pattern','?')} -> {len(result)} results[/dim]")
            elif name == "search_codebase":
                console.print(f"[dim]  semantic: {args.get('query','?')[:60]} -> {len(result)} chars[/dim]")

            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": result[:4000]})

            if name in ("str_replace_in_file", "write_file") and ok:
                code_changes.append({"tool": name, "file": args.get("path", "unknown")})

    console.print(f"[dim]  Coder done — {len(code_changes)} edit(s): {[c['file'] for c in code_changes]}[/dim]")
    return {"messages": messages, "code_changes": code_changes, "total_tokens": tokens}