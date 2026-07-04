"""
config.py — Unified DevRAG configuration.

Two access styles are supported so both halves of the codebase work unchanged:

  1. Pydantic settings object (RAG engine, API):
       from devrag.config import settings
       settings.embedding_model

  2. Module-level constants (agent nodes, tools):
       from devrag import config
       config.MAX_RETRIES
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# Load .env from the project root (parent of the devrag package)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # LLM — Claude first, other providers as fallback
    # ------------------------------------------------------------------
    anthropic_api_key: str = Field("", env="ANTHROPIC_API_KEY")
    model_primary: str = Field("claude-sonnet-5", env="MODEL_PRIMARY")
    model_fast: str = Field("claude-haiku-4-5", env="MODEL_FAST")
    # Optional override for the hardest (architect-level) tasks, e.g. claude-opus-4-8
    model_architect: str = Field("", env="MODEL_ARCHITECT")
    # auto | anthropic | groq | mistral | ollama
    llm_provider: str = Field("auto", env="LLM_PROVIDER")

    # Fallback providers (optional)
    groq_api_key: str = Field("", env="GROQ_API_KEY")
    groq_model: str = Field("llama-3.3-70b-versatile", env="GROQ_MODEL")
    mistral_api_key: str = Field("", env="MISTRAL_API_KEY")
    mistral_model: str = Field("mistral-small-latest", env="MISTRAL_MODEL")
    ollama_host: str = Field("http://localhost:11434", env="OLLAMA_HOST")
    ollama_model: str = Field("qwen2.5-coder:7b", env="OLLAMA_MODEL")

    max_tokens: int = Field(8192, env="MAX_TOKENS")

    # ------------------------------------------------------------------
    # RAG — retrieval engine
    # ------------------------------------------------------------------
    embedding_model: str = Field("microsoft/codebert-base", env="EMBEDDING_MODEL")
    reranker_model: str = Field("cross-encoder/ms-marco-MiniLM-L-6-v2", env="RERANKER_MODEL")
    faiss_index_path: Path = Field(Path("data/processed/faiss_index"), env="FAISS_INDEX_PATH")
    chunk_size: int = Field(512, env="CHUNK_SIZE")
    chunk_overlap: int = Field(64, env="CHUNK_OVERLAP")
    top_k_retrieve: int = Field(20, env="TOP_K_RETRIEVE")
    top_k_rerank: int = Field(5, env="TOP_K_RERANK")
    faithfulness_threshold: float = Field(0.5, env="FAITHFULNESS_THRESHOLD")

    # ------------------------------------------------------------------
    # Agent
    # ------------------------------------------------------------------
    github_token: str = Field("", env="GITHUB_TOKEN")
    max_retries: int = Field(5, env="MAX_RETRIES")
    sandbox_timeout: int = Field(120, env="SANDBOX_TIMEOUT")
    clone_dir: Path = Field(Path("/tmp/devrag_repos"), env="CLONE_DIR")
    enable_self_review: bool = Field(True, env="ENABLE_SELF_REVIEW")
    enable_hierarchical_planning: bool = Field(True, env="ENABLE_HIERARCHICAL_PLANNING")
    enable_complexity_routing: bool = Field(True, env="ENABLE_COMPLEXITY_ROUTING")
    max_subtasks: int = Field(10, env="MAX_SUBTASKS")

    # ------------------------------------------------------------------
    # API / tracking
    # ------------------------------------------------------------------
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8001, env="API_PORT")
    allowed_origins: str = Field("*", env="ALLOWED_ORIGINS")
    api_key: str = Field("", env="API_KEY")
    mlflow_tracking_uri: str = Field("http://localhost:5000", env="MLFLOW_TRACKING_URI")
    mlflow_experiment: str = Field("devrag", env="MLFLOW_EXPERIMENT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

def get_available_providers() -> dict:
    """Which LLM providers have credentials configured."""
    return {
        "anthropic": bool(settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")),
        "groq": bool(settings.groq_api_key),
        "mistral": bool(settings.mistral_api_key),
        "ollama": True,  # assumed available if the daemon is running
    }


def get_primary_provider() -> str:
    """Resolve the provider to use: explicit setting, else first with a key."""
    if settings.llm_provider != "auto":
        return settings.llm_provider
    providers = get_available_providers()
    for name in ("anthropic", "groq", "mistral", "ollama"):
        if providers.get(name):
            return name
    return "anthropic"


def validate() -> None:
    """Fail fast when nothing is configured."""
    providers = get_available_providers()
    if not (providers["anthropic"] or providers["groq"] or providers["mistral"]):
        raise EnvironmentError(
            "No LLM API key configured.\n"
            "Set ANTHROPIC_API_KEY (recommended) in .env — or GROQ_API_KEY / "
            "MISTRAL_API_KEY as a fallback.\n"
            "Copy .env.example to .env and fill in your keys."
        )


class _CfgShim:
    """Backwards-compatible shim: cfg.validate() etc."""

    @staticmethod
    def validate() -> None:
        validate()


cfg = _CfgShim()


# ---------------------------------------------------------------------------
# Module-level constants — the interface DevAgent-origin code expects
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
MODEL_PRIMARY = settings.model_primary
MODEL_FAST = settings.model_fast
MODEL_ARCHITECT = settings.model_architect
LLM_PROVIDER = settings.llm_provider

GROQ_API_KEY = settings.groq_api_key
GROQ_MODEL = settings.groq_model
MISTRAL_API_KEY = settings.mistral_api_key
MISTRAL_MODEL = settings.mistral_model
OLLAMA_HOST = settings.ollama_host
OLLAMA_MODEL = settings.ollama_model

MAX_TOKENS = settings.max_tokens
GITHUB_TOKEN = settings.github_token or os.environ.get("GITHUB_TOKEN", "")

MAX_RETRIES = settings.max_retries
SANDBOX_TIMEOUT = settings.sandbox_timeout
CLONE_DIR = settings.clone_dir

# File handling limits (from DevAgent)
TOOL_OUTPUT_LIMIT = 12_000
FILE_SIZE_LIMIT_FOR_WRITE = 8_000

DEBUG = os.environ.get("DEVRAG_DEBUG", "0") == "1"

ENABLE_COMPLEXITY_ROUTING = settings.enable_complexity_routing
ENABLE_SELF_REVIEW = settings.enable_self_review
ENABLE_HIERARCHICAL_PLANNING = settings.enable_hierarchical_planning
MAX_SUBTASKS = settings.max_subtasks

CLONE_DIR.mkdir(parents=True, exist_ok=True)
