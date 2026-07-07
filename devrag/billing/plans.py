"""
plans.py — Tier definitions and pricing.

Two tiers. Free covers real evaluation of the product; Pro unlocks the
things that deliver ongoing value: unlimited usage, the full issue-to-PR
pipeline, and architect-model routing.

Prices are value-anchored, not cost-anchored: one Pro month costs less than
the developer-hour a single automated PR fix saves.

Razorpay expects amounts in the smallest currency unit (paise / cents).
INR is the domestic price, USD the international one — same Orders API,
same checkout, currency chosen at order time.
"""
from __future__ import annotations

TIER_FREE = "free"
TIER_PRO = "pro"

# Free-tier limits
FREE_MAX_REPOS = 2
FREE_QUERIES_PER_DAY = 25
FREE_AGENT_RUNS_PER_MONTH = 5

# Packages purchasable via Razorpay. Amounts in paise / cents.
PACKAGES = {
    "pro_monthly": {
        "name": "DevRAG Pro — Monthly",
        "days": 31,
        "prices": {"INR": 19900, "USD": 399},        # Rs 199 / $3.99
        "display": {"INR": "Rs 199/month", "USD": "$3.99/month"},
    },
    "pro_yearly": {
        "name": "DevRAG Pro — Yearly",
        "days": 366,
        "prices": {"INR": 199900, "USD": 3999},      # Rs 1,999 / $39.99 (2 months free)
        "display": {"INR": "Rs 1,999/year", "USD": "$39.99/year"},
    },
}

SUPPORTED_CURRENCIES = ("INR", "USD")

TIER_FEATURES = {
    TIER_FREE: [
        f"Index up to {FREE_MAX_REPOS} repositories",
        f"{FREE_QUERIES_PER_DAY} chat queries per day with citations and faithfulness scores",
        f"{FREE_AGENT_RUNS_PER_MONTH} agent runs per month (local tasks and dry runs)",
        "Hybrid retrieval: CodeBERT + FAISS + BM25 + reranking",
        "Bring your own LLM keys (Claude, Groq, Mistral, Ollama)",
    ],
    TIER_PRO: [
        "Unlimited repositories and chat queries",
        "Unlimited agent runs, including GitHub issue to pull request",
        "Architect-model routing for the hardest tasks (Opus-tier)",
        "Run history export and per-run cost analytics",
        "Priority support and early access to the GitHub App and MCP server",
    ],
}


def get_plans() -> dict:
    """Serializable pricing catalog for the API and frontend."""
    return {
        "tiers": {
            TIER_FREE: {"name": "Free", "features": TIER_FEATURES[TIER_FREE]},
            TIER_PRO: {"name": "Pro", "features": TIER_FEATURES[TIER_PRO]},
        },
        "packages": {
            key: {
                "name": p["name"],
                "days": p["days"],
                "prices": p["prices"],
                "display": p["display"],
            }
            for key, p in PACKAGES.items()
        },
        "currencies": list(SUPPORTED_CURRENCIES),
        "limits": {
            "free_max_repos": FREE_MAX_REPOS,
            "free_queries_per_day": FREE_QUERIES_PER_DAY,
            "free_agent_runs_per_month": FREE_AGENT_RUNS_PER_MONTH,
        },
    }
