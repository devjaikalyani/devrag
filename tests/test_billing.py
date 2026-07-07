"""
test_billing.py — Tiers, entitlements, usage limits, and Razorpay signatures.
No network calls; the entitlement store is redirected to a temp directory.
"""
import hashlib
import hmac
import json
import sys
import os
import pathlib
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from devrag.billing import entitlements, plans


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Point the entitlement/usage store at a temp dir for every test."""
    monkeypatch.setattr(entitlements, "BILLING_DIR", tmp_path)
    monkeypatch.setattr(entitlements, "ENTITLEMENT_FILE", tmp_path / "entitlement.json")
    monkeypatch.setattr(entitlements, "USAGE_FILE", tmp_path / "usage.json")
    yield


class TestPlans:
    def test_catalog_shape(self):
        catalog = plans.get_plans()
        assert set(catalog["tiers"]) == {"free", "pro"}
        assert set(catalog["packages"]) == {"pro_monthly", "pro_yearly"}
        assert catalog["currencies"] == ["INR", "USD"]

    def test_prices_match_positioning(self):
        monthly = plans.PACKAGES["pro_monthly"]["prices"]
        assert monthly["INR"] == 19900     # Rs 199
        assert monthly["USD"] == 399       # $3.99
        yearly = plans.PACKAGES["pro_yearly"]["prices"]
        # Yearly costs less than 12x monthly in both currencies
        assert yearly["INR"] < 12 * monthly["INR"]
        assert yearly["USD"] < 12 * monthly["USD"]


class TestEntitlements:
    def test_defaults_to_free(self):
        assert entitlements.get_tier() == "free"
        assert not entitlements.is_pro()

    def test_activation_grants_pro(self):
        record = entitlements.activate_pro("pro_monthly", "pay_x", "order_x", "INR")
        assert record["tier"] == "pro"
        assert entitlements.is_pro()
        expires = datetime.fromisoformat(record["expires_at"])
        assert expires > datetime.now() + timedelta(days=29)

    def test_expired_pro_reverts_to_free(self):
        entitlements._write_json(entitlements.ENTITLEMENT_FILE, {
            "tier": "pro",
            "expires_at": (datetime.now() - timedelta(days=1)).isoformat(),
        })
        assert entitlements.get_tier() == "free"

    def test_repurchase_extends_expiry(self):
        first = entitlements.activate_pro("pro_monthly", "pay_1", "order_1", "INR")
        second = entitlements.activate_pro("pro_monthly", "pay_2", "order_2", "INR")
        assert second["expires_at"] > first["expires_at"]


class TestFreeLimits:
    def test_query_limit_enforced(self):
        for _ in range(plans.FREE_QUERIES_PER_DAY):
            entitlements.check_query_allowed()
        with pytest.raises(entitlements.EntitlementError):
            entitlements.check_query_allowed()

    def test_agent_run_limit_enforced(self):
        for _ in range(plans.FREE_AGENT_RUNS_PER_MONTH):
            entitlements.check_agent_run_allowed()
        with pytest.raises(entitlements.EntitlementError):
            entitlements.check_agent_run_allowed()

    def test_pr_mode_requires_pro(self):
        with pytest.raises(entitlements.EntitlementError):
            entitlements.check_agent_run_allowed(issue_mode_with_pr=True)

    def test_repo_limit_enforced(self):
        entitlements.check_repo_allowed(current_repo_count=1, is_new_repo=True)
        with pytest.raises(entitlements.EntitlementError):
            entitlements.check_repo_allowed(
                current_repo_count=plans.FREE_MAX_REPOS, is_new_repo=True
            )

    def test_existing_repo_always_allowed(self):
        entitlements.check_repo_allowed(current_repo_count=99, is_new_repo=False)

    def test_pro_bypasses_all_limits(self):
        entitlements.activate_pro("pro_monthly", "pay_x", "order_x", "USD")
        for _ in range(plans.FREE_QUERIES_PER_DAY + 5):
            entitlements.check_query_allowed()
        entitlements.check_agent_run_allowed(issue_mode_with_pr=True)
        entitlements.check_repo_allowed(current_repo_count=99, is_new_repo=True)

    def test_status_reports_remaining(self):
        entitlements.check_query_allowed()
        s = entitlements.status()
        assert s["tier"] == "free"
        assert s["remaining"]["queries_today"] == plans.FREE_QUERIES_PER_DAY - 1


class TestSignatures:
    def test_payment_signature_roundtrip(self, monkeypatch):
        from devrag.billing import razorpay_client
        from devrag.config import settings

        monkeypatch.setattr(settings, "razorpay_key_id", "rzp_test_key")
        monkeypatch.setattr(settings, "razorpay_key_secret", "test_secret")

        order_id, payment_id = "order_ABC123", "pay_XYZ789"
        good = hmac.new(b"test_secret", f"{order_id}|{payment_id}".encode(),
                        hashlib.sha256).hexdigest()
        assert razorpay_client.verify_payment_signature(order_id, payment_id, good)
        assert not razorpay_client.verify_payment_signature(order_id, payment_id, "forged")

    def test_webhook_signature_roundtrip(self, monkeypatch):
        from devrag.billing import razorpay_client
        from devrag.config import settings

        monkeypatch.setattr(settings, "razorpay_webhook_secret", "hook_secret")

        body = json.dumps({"event": "payment.captured"}).encode()
        good = hmac.new(b"hook_secret", body, hashlib.sha256).hexdigest()
        assert razorpay_client.verify_webhook_signature(body, good)
        assert not razorpay_client.verify_webhook_signature(body, "forged")

    def test_unconfigured_raises(self, monkeypatch):
        from devrag.billing import razorpay_client
        from devrag.config import settings

        monkeypatch.setattr(settings, "razorpay_key_id", "")
        monkeypatch.setattr(settings, "razorpay_key_secret", "")
        with pytest.raises(razorpay_client.RazorpayNotConfigured):
            razorpay_client.verify_payment_signature("o", "p", "s")
