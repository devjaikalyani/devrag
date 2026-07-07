"""
test_repo_permission.py — Safety interlock for the agent's PR mode.

PR-mode runs against repositories the token user does not own must be refused
unless ALLOW_THIRD_PARTY_REPOS is explicitly set. Unsolicited automated pull
requests to third-party repos violate GitHub's Acceptable Use Policies.
"""
import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from devrag.agent import runner
from devrag import config


@pytest.fixture
def owned_login(monkeypatch):
    monkeypatch.setattr(
        "devrag.tools.github_client.get_authenticated_login", lambda: "devuser"
    )


class TestRepoPermission:
    def test_owner_pr_allowed(self, owned_login, monkeypatch):
        monkeypatch.setattr(config, "ALLOW_THIRD_PARTY_REPOS", False)
        runner._check_repo_permission("devuser", pr_mode=True)  # own repo, no raise

    def test_owner_case_insensitive(self, owned_login, monkeypatch):
        monkeypatch.setattr(config, "ALLOW_THIRD_PARTY_REPOS", False)
        runner._check_repo_permission("DevUser", pr_mode=True)

    def test_third_party_pr_refused(self, owned_login, monkeypatch):
        monkeypatch.setattr(config, "ALLOW_THIRD_PARTY_REPOS", False)
        with pytest.raises(PermissionError):
            runner._check_repo_permission("pallets", pr_mode=True)

    def test_third_party_no_pr_allowed(self, owned_login, monkeypatch):
        # dry run / no_pr sets pr_mode=False — reading and fixing is fine
        monkeypatch.setattr(config, "ALLOW_THIRD_PARTY_REPOS", False)
        runner._check_repo_permission("pallets", pr_mode=False)

    def test_third_party_pr_allowed_with_optin(self, owned_login, monkeypatch):
        monkeypatch.setattr(config, "ALLOW_THIRD_PARTY_REPOS", True)
        runner._check_repo_permission("pallets", pr_mode=True)

    def test_unknown_identity_does_not_block(self, monkeypatch):
        # If GitHub identity can't be resolved, don't hard-fail here;
        # the clone/PR steps surface auth errors instead.
        monkeypatch.setattr(config, "ALLOW_THIRD_PARTY_REPOS", False)

        def boom():
            raise RuntimeError("GITHUB_TOKEN not set")

        monkeypatch.setattr(
            "devrag.tools.github_client.get_authenticated_login", boom
        )
        runner._check_repo_permission("pallets", pr_mode=True)
