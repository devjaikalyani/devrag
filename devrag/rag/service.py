"""
service.py — Process-wide singleton for the RAG pipeline.

Both surfaces of DevRAG share one pipeline instance (and therefore one set of
per-repo indexes):

  - the API/chat surface (devrag.api.main)
  - the agent tools (devrag.tools.rag_search) used inside LangGraph nodes

The heavy models (CodeBERT, cross-encoder, NLI) load once, lazily.
"""
from __future__ import annotations

import threading
from typing import Optional

from loguru import logger

from devrag.rag.pipeline import CodeRAGPipeline

_pipeline: Optional[CodeRAGPipeline] = None
_lock = threading.Lock()


def get_pipeline() -> CodeRAGPipeline:
    """Get or lazily create the shared pipeline."""
    global _pipeline
    if _pipeline is None:
        with _lock:
            if _pipeline is None:
                logger.info("Initializing DevRAG pipeline (models load on first use)...")
                _pipeline = CodeRAGPipeline.from_config()
    return _pipeline


def pipeline_ready() -> bool:
    return _pipeline is not None
