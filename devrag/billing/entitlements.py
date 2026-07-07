"""
entitlements.py — Current tier, expiry, and free-tier usage limits.

Self-hosted DevRAG stores one entitlement per installation in
data/billing/entitlement.json; a hosted deployment can swap this store for
a per-user database without touching the enforcement call sites.

Enforcement raises EntitlementError with a human-readable reason; the API
layer converts it to HTTP 402 so the frontend can route users to /pricing.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from devrag.billing import plans

BILLING_DIR = Path(__file__).resolve().parents[2] / "data" / "billing"
ENTITLEMENT_FILE = BILLING_DIR / "entitlement.json"
USAGE_FILE = BILLING_DIR / "usage.json"

_lock = threading.Lock()


class EntitlementError(Exception):
    """Raised when an action exceeds the current tier. Maps to HTTP 402."""


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _write_json(path: Path, data: dict) -> None:
    BILLING_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Tier
# ---------------------------------------------------------------------------

def get_entitlement() -> dict:
    """Current entitlement record; defaults to free."""
    record = _read_json(ENTITLEMENT_FILE)
    if record.get("tier") == plans.TIER_PRO:
        expires = record.get("expires_at", "")
        if expires and expires < datetime.now().isoformat():
            logger.info("Pro entitlement expired; reverting to free tier")
            return {"tier": plans.TIER_FREE, "expired_pro": record}
        return record
    return {"tier": plans.TIER_FREE}


def get_tier() -> str:
    return get_entitlement().get("tier", plans.TIER_FREE)


def is_pro() -> bool:
    return get_tier() == plans.TIER_PRO


def activate_pro(package: str, payment_id: str, order_id: str, currency: str) -> dict:
    """Grant (or extend) Pro after a verified payment."""
    pkg = plans.PACKAGES[package]
    now = datetime.now()

    # Extend from the current expiry when already Pro (stacking purchases)
    current = _read_json(ENTITLEMENT_FILE)
    base = now
    if current.get("tier") == plans.TIER_PRO:
        try:
            existing = datetime.fromisoformat(current["expires_at"])
            if existing > now:
                base = existing
        except Exception:
            pass

    record = {
        "tier": plans.TIER_PRO,
        "package": package,
        "currency": currency,
        "activated_at": now.isoformat(timespec="seconds"),
        "expires_at": (base + timedelta(days=pkg["days"])).isoformat(timespec="seconds"),
        "payment_id": payment_id,
        "order_id": order_id,
    }
    with _lock:
        _write_json(ENTITLEMENT_FILE, record)
    logger.info(f"Pro activated: {package} until {record['expires_at']}")
    return record


# ---------------------------------------------------------------------------
# Free-tier usage counters (rolling day / month windows)
# ---------------------------------------------------------------------------

def _usage() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    month = today[:7]
    u = _read_json(USAGE_FILE)
    if u.get("date") != today:
        u["date"] = today
        u["queries_today"] = 0
    if u.get("month") != month:
        u["month"] = month
        u["runs_this_month"] = 0
    return u


def get_usage() -> dict:
    u = _usage()
    return {
        "queries_today": u.get("queries_today", 0),
        "runs_this_month": u.get("runs_this_month", 0),
    }


def check_query_allowed() -> None:
    """Free tier: FREE_QUERIES_PER_DAY chat queries per day."""
    if is_pro():
        return
    with _lock:
        u = _usage()
        if u.get("queries_today", 0) >= plans.FREE_QUERIES_PER_DAY:
            raise EntitlementError(
                f"Free tier limit reached: {plans.FREE_QUERIES_PER_DAY} queries per day. "
                f"Upgrade to Pro for unlimited queries."
            )
        u["queries_today"] = u.get("queries_today", 0) + 1
        _write_json(USAGE_FILE, u)


def check_agent_run_allowed(issue_mode_with_pr: bool = False) -> None:
    """Free tier: FREE_AGENT_RUNS_PER_MONTH runs per month; PR mode is Pro-only."""
    if is_pro():
        return
    if issue_mode_with_pr:
        raise EntitlementError(
            "Opening pull requests from GitHub issues is a Pro feature. "
            "Free tier supports local tasks, dry runs, and no-PR issue runs."
        )
    with _lock:
        u = _usage()
        if u.get("runs_this_month", 0) >= plans.FREE_AGENT_RUNS_PER_MONTH:
            raise EntitlementError(
                f"Free tier limit reached: {plans.FREE_AGENT_RUNS_PER_MONTH} agent runs per month. "
                f"Upgrade to Pro for unlimited runs."
            )
        u["runs_this_month"] = u.get("runs_this_month", 0) + 1
        _write_json(USAGE_FILE, u)


def check_repo_allowed(current_repo_count: int, is_new_repo: bool) -> None:
    """Free tier: at most FREE_MAX_REPOS indexed repositories."""
    if is_pro() or not is_new_repo:
        return
    if current_repo_count >= plans.FREE_MAX_REPOS:
        raise EntitlementError(
            f"Free tier limit reached: {plans.FREE_MAX_REPOS} indexed repositories. "
            f"Delete one or upgrade to Pro for unlimited repositories."
        )


def status() -> dict:
    """Billing status for the API: tier, expiry, remaining free quota."""
    ent = get_entitlement()
    usage = get_usage()
    out = {
        "tier": ent.get("tier", plans.TIER_FREE),
        "expires_at": ent.get("expires_at"),
        "package": ent.get("package"),
        "usage": usage,
    }
    if out["tier"] == plans.TIER_FREE:
        out["remaining"] = {
            "queries_today": max(0, plans.FREE_QUERIES_PER_DAY - usage["queries_today"]),
            "runs_this_month": max(0, plans.FREE_AGENT_RUNS_PER_MONTH - usage["runs_this_month"]),
        }
    return out
