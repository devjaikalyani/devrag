"""
rag_search.py — Semantic code search for the agent, backed by the shared
hybrid retrieval pipeline (CodeBERT + FAISS + BM25 + RRF + cross-encoder).

This replaces DevAgent's TF-IDF CodebaseIndex. The agent's explorer node and
the coder/debugger tool loops call into the same per-repo indexes that power
the chat surface, so understanding is shared across both.

All functions degrade gracefully: if the index cannot be built (missing
models, offline, etc.) they return empty results and the agent falls back to
file reads and grep.
"""
from __future__ import annotations

from typing import Optional

from loguru import logger


def ensure_repo_indexed(repo_path: str) -> Optional[str]:
    """Ingest (or switch to) the index for a local repo. Returns key or None."""
    try:
        from devrag.rag.service import get_pipeline

        pipeline = get_pipeline()
        key = pipeline.ensure_ingested(repo_path)
        return key
    except Exception as e:
        logger.warning(f"RAG indexing unavailable for {repo_path}: {e}")
        return None


def retrieve_chunks(query: str, top_k: int = 5) -> list[dict]:
    """Hybrid retrieval against the active repo index.

    Returns a list of dicts: {source, start_line, end_line, language, text, score}.
    """
    try:
        from devrag.rag.service import get_pipeline

        pipeline = get_pipeline()
        if pipeline.retriever is None:
            return []
        results = pipeline.retriever.retrieve(query)[:top_k]
        return [
            {
                "source": r.chunk.source,
                "start_line": r.chunk.start_line,
                "end_line": r.chunk.end_line,
                "language": r.chunk.language or "text",
                "text": r.chunk.text,
                "score": round(r.rerank_score, 4),
            }
            for r in results
        ]
    except Exception as e:
        logger.warning(f"RAG retrieval failed: {e}")
        return []


def format_chunks(chunks: list[dict], header: str = "RETRIEVED CODE (semantically relevant)") -> str:
    """Format retrieved chunks as a context block for an LLM prompt."""
    if not chunks:
        return ""
    parts = [f"### {header}"]
    for c in chunks:
        parts.append(
            f"#### `{c['source']}` (lines {c['start_line']}-{c['end_line']}, score {c['score']})\n"
            f"```{c['language']}\n{c['text']}\n```"
        )
    return "\n\n".join(parts)


def search_codebase(query: str, top_k: int = 5) -> str:
    """Tool-facing semantic search. Returns a formatted string of matches."""
    chunks = retrieve_chunks(query, top_k=top_k)
    if not chunks:
        return "No semantic matches found. Try search_code with a literal pattern instead."
    lines = [f"Semantic search results for: {query}"]
    for i, c in enumerate(chunks, 1):
        preview = " ".join(c["text"].split())[:200]
        lines.append(
            f"{i}. {c['source']}:{c['start_line']}-{c['end_line']} (score {c['score']})\n   {preview}"
        )
    return "\n".join(lines)


# OpenAI-style tool schema for the coder/debugger loops
SEARCH_CODEBASE_TOOL = {
    "type": "function",
    "function": {
        "name": "search_codebase",
        "description": (
            "Semantic search over the whole repository. Use natural language to find "
            "where behavior is implemented, e.g. 'function that validates email addresses'. "
            "Prefer this over search_code when you do not know the exact symbol name."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language description of the code to find"},
            },
            "required": ["query"],
        },
    },
}
