"""
test_graph_routing.py — Tests for LangGraph conditional routing logic.
"""
import sys
import os
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("GITHUB_TOKEN", "test_token")

from devrag import config
from devrag.agent.graph import route_after_test, route_after_review, route_by_complexity


class TestRouteAfterTest:
    def test_routes_to_review_on_pass(self):
        state = {"test_passed": True, "retry_count": 0}
        assert route_after_test(state) == "review"

    def test_routes_to_debug_on_fail_with_retries_remaining(self):
        state = {"test_passed": False, "retry_count": 2}
        assert route_after_test(state) == "debug"

    def test_routes_to_failed_on_max_retries(self):
        state = {"test_passed": False, "retry_count": config.MAX_RETRIES + 1}
        assert route_after_test(state) == "failed"

    def test_routes_to_debug_on_first_failure(self):
        state = {"test_passed": False, "retry_count": 0}
        assert route_after_test(state) == "debug"

    def test_routes_to_failed_just_at_limit(self):
        state = {"test_passed": False, "retry_count": config.MAX_RETRIES}
        assert route_after_test(state) == "failed"


class TestRouteAfterReview:
    def test_routes_to_open_pr_when_review_passes(self):
        state = {"review_passed": True, "no_pr": False}
        assert route_after_review(state) == "open_pr"

    def test_routes_to_done_when_no_pr(self):
        state = {"review_passed": True, "no_pr": True}
        assert route_after_review(state) == "done"

    def test_routes_to_code_on_blocking_review_issues(self):
        state = {"review_passed": False, "no_pr": False,
                 "review_issues": ["ERROR: introduces regression"]}
        assert route_after_review(state) == "code"

    def test_non_blocking_issues_still_open_pr(self):
        state = {"review_passed": False, "no_pr": False,
                 "review_issues": ["minor style nit"]}
        assert route_after_review(state) == "open_pr"

    def test_review_loop_capped_after_two_cycles(self):
        state = {"review_passed": False, "no_pr": False, "review_count": 2,
                 "review_issues": ["ERROR: still unhappy"]}
        assert route_after_review(state) == "open_pr"

    def test_review_loop_capped_respects_no_pr(self):
        state = {"review_passed": False, "no_pr": True, "review_count": 2,
                 "review_issues": ["ERROR: still unhappy"]}
        assert route_after_review(state) == "done"


class TestRouteByComplexity:
    def test_simple_issue_goes_to_explore(self):
        state = {"complexity": None, "issue_title": "Fix typo in docstring",
                 "issue_body": "One word is misspelled.", "files_to_edit": []}
        assert route_by_complexity(state) == "explore"

    def test_explicit_complex_goes_to_decompose(self):
        from devrag.llm.router import TaskComplexity
        state = {"complexity": TaskComplexity.COMPLEX}
        assert route_by_complexity(state) == "decompose"
