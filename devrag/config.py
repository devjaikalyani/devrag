"""
config.py: Unified DevRAG configuration.

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
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env from the project root (parent of the devrag package)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    # Field names double as env var names (case-insensitive), so
    # anthropic_api_key reads ANTHROPIC_API_KEY and so on.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # LLM: Claude first, other providers as fallback
    # ------------------------------------------------------------------
    anthropic_api_key: str = ""
    model_primary: str = "claude-sonnet-5"
    model_fast: str = "claude-haiku-4-5"
    # Optional override for the hardest (architect-level) tasks, e.g. claude-opus-4-8
    model_architect: str = ""
    # auto | anthropic | groq | mistral | ollama
    llm_provider: str = "auto"

    # Fallback providers (optional)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"

    max_tokens: int = 8192

    # ------------------------------------------------------------------
    # RAG: retrieval engine
    # ------------------------------------------------------------------
    embedding_model: str = "microsoft/codebert-base"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    faiss_index_path: Path = Path("data/processed/faiss_index")
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k_retrieve: int = 20
    top_k_rerank: int = 5
    faithfulness_threshold: float = 0.5

    # ------------------------------------------------------------------
    # Agent
    # ------------------------------------------------------------------
    github_token: str = ""
    # Safety interlock: PR-mode runs against repos the token user does not own
    # are refused unless this is explicitly enabled. Unsolicited automated PRs
    # to third-party repositories violate GitHub's Acceptable Use Policies.
    allow_third_party_repos: bool = False
    max_retries: int = 5
    sandbox_timeout: int = 120
    clone_dir: Path = Path("/tmp/devrag_repos")
    enable_self_review: bool = True
    enable_hierarchical_planning: bool = True
    enable_complexity_routing: bool = True
    max_subtasks: int = 10

    # ------------------------------------------------------------------
    # Billing (Razorpay: domestic INR and international USD)
    # ------------------------------------------------------------------
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # ------------------------------------------------------------------
    # API / tracking
    # ------------------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    allowed_origins: str = "*"
    api_key: str = ""
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment: str = "devrag"


settings = Settings()


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

_ollama_probe = {"ts": 0.0, "alive": False}


def _ollama_reachable() -> bool:
    """Probe the Ollama daemon, cached for 30s so /health stays cheap."""
    now = time.time()
    if now - _ollama_probe["ts"] < 30:
        return _ollama_probe["alive"]
    try:
        with urllib.request.urlopen(settings.ollama_host.rstrip("/") + "/api/tags", timeout=1):
            alive = True
    except Exception:
        alive = False
    _ollama_probe.update(ts=now, alive=alive)
    return alive


def get_available_providers() -> dict:
    """Which LLM providers are usable: keyed providers by config, Ollama by liveness."""
    return {
        "anthropic": bool(settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")),
        "groq": bool(settings.groq_api_key),
        "mistral": bool(settings.mistral_api_key),
        "ollama": _ollama_reachable(),
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
            "Set ANTHROPIC_API_KEY (recommended) in .env, or GROQ_API_KEY / "
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
# Module-level constants: the interface DevAgent-origin code expects
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
ALLOW_THIRD_PARTY_REPOS = settings.allow_third_party_repos

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
