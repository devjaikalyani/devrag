# DevRAG: chat with any codebase, then let the agent fix it.
#
# Subpackages:
#   devrag.rag      hybrid retrieval engine (CodeBERT + FAISS + BM25 + rerank)
#   devrag.agent    LangGraph autonomous agent (plan / explore / code / test)
#   devrag.llm      Claude-first LLM client with provider fallback
#   devrag.api      FastAPI app (chat, ingestion, agent runs, billing)
#   devrag.billing  Razorpay tiers and entitlements
#   devrag.tools    filesystem, bash, GitHub, and RAG-search tools
#
# Kept import-free: submodules pull in heavy ML dependencies, so import the
# piece you need (e.g. `from devrag.rag.service import get_pipeline`).
