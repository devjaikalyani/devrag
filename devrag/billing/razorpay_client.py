"""
razorpay_client.py — Razorpay Orders integration.

One integration covers both markets:
  - Domestic (India): INR orders — UPI, cards, netbanking, wallets
  - International: USD orders — international cards (enable International
    Payments in the Razorpay dashboard)

Flow (order-based, no auto-renew):
  1. Frontend: POST /billing/order {package, currency} -> {order_id, key_id, amount}
  2. Frontend opens Razorpay Checkout with that order_id
  3. On success, Checkout returns payment_id + signature
  4. Frontend: POST /billing/verify -> HMAC check -> Pro activated locally
  5. (Hosted deployments) POST /billing/webhook handles payment.captured
     server-to-server as the source of truth

Signature rules (Razorpay docs):
  payment:  HMAC_SHA256(order_id + "|" + payment_id, key_secret)
  webhook:  HMAC_SHA256(raw_body, webhook_secret) vs X-Razorpay-Signature
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from typing import Optional

from loguru import logger

from devrag.config import settings
from devrag.billing import plans


class RazorpayNotConfigured(Exception):
    """Raised when RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are missing."""


def _require_keys() -> tuple[str, str]:
    key_id = settings.razorpay_key_id
    key_secret = settings.razorpay_key_secret
    if not key_id or not key_secret:
        raise RazorpayNotConfigured(
            "Razorpay is not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env "
            "(get keys at https://dashboard.razorpay.com/app/website-app-settings/api-keys)."
        )
    return key_id, key_secret


def _client():
    import razorpay

    key_id, key_secret = _require_keys()
    return razorpay.Client(auth=(key_id, key_secret))


def create_order(package: str, currency: str) -> dict:
    """Create a Razorpay order for a Pro package. Returns checkout payload."""
    if package not in plans.PACKAGES:
        raise ValueError(f"Unknown package: {package}")
    if currency not in plans.SUPPORTED_CURRENCIES:
        raise ValueError(f"Unsupported currency: {currency}. Use one of {plans.SUPPORTED_CURRENCIES}.")

    pkg = plans.PACKAGES[package]
    amount = pkg["prices"][currency]

    order = _client().order.create({
        "amount": amount,
        "currency": currency,
        "receipt": f"devrag_{uuid.uuid4().hex[:20]}",   # <= 40 chars
        "notes": {"package": package, "product": "devrag_pro"},
    })
    logger.info(f"Razorpay order created: {order['id']} {amount} {currency} ({package})")

    return {
        "order_id": order["id"],
        "amount": amount,
        "currency": currency,
        "package": package,
        "key_id": settings.razorpay_key_id,
        "name": "DevRAG Pro",
        "description": pkg["name"],
    }


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Constant-time HMAC verification of a checkout success callback."""
    _, key_secret = _require_keys()
    expected = hmac.new(
        key_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """Verify X-Razorpay-Signature on a webhook delivery."""
    secret = settings.razorpay_webhook_secret
    if not secret:
        raise RazorpayNotConfigured(
            "RAZORPAY_WEBHOOK_SECRET is not set. Configure a webhook secret in the "
            "Razorpay dashboard and mirror it in .env."
        )
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def fetch_order_package(order_id: str) -> Optional[str]:
    """Read the package name back from the order's notes (webhook path)."""
    try:
        order = _client().order.fetch(order_id)
        return (order.get("notes") or {}).get("package")
    except Exception as e:
        logger.warning(f"Could not fetch Razorpay order {order_id}: {e}")
        return None
