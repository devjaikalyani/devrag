"""
Agent node tests — each node in isolation with the LLM layer mocked.
No real API calls.
"""
from __future__ import annotations

import sys
import os
import pathlib
from unittest.mock import MagicMock, patch
from pathlib import Path

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("GITHUB_TOKEN", "test_token")


def make_base_state(tmp_path: Path) -> dict:
    """Build a minimal AgentState for testing."""
    return {
        "issue_url": "https://github.com/test/repo/issues/1",
        "issue_number": 1,
        "issue_title": "Fix division by zero in calculator",
        "issue_body": "When dividing by zero, the app crashes with ZeroDivisionError.",
        "repo_owner": "test",
        "repo_name": "repo",
        "repo_path": str(tmp_path),
        "action_plan": [],
        "files_to_edit": [],
        "messages": [],
        "code_changes": [],
        "test_output": None,
        "test_passed": False,
        "retry_count": 0,
        "branch_name": "devrag/fix-1-test",
        "pr_url": None,
        "error": None,
        "total_tokens": 0,
        "no_pr": True,
    }


def _llm_msg(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = []
    return msg


class TestPlannerNode:
    def test_planner_produces_plan(self, tmp_path):
        """Planner should return action_plan and files_to_edit from the LLM JSON."""
        (tmp_path / "calculator.py").write_text("def divide(a, b): return a / b")

        plan_json = (
            '{"action_plan": ["Read calculator.py", "Add zero check"],'
            ' "files_to_edit": ["calculator.py"],'
            ' "test_command": "python -m pytest tests/ -v",'
            ' "reasoning": "Missing division by zero check."}'
        )
        with patch("devrag.agent.planner.chat", return_value=(_llm_msg(plan_json), 150)):
            from devrag.agent.planner import planner_node

            result = planner_node(make_base_state(tmp_path))

        assert result["action_plan"] == ["Read calculator.py", "Add zero check"]
        assert result["files_to_edit"] == ["calculator.py"]
        assert result["test_command"] == "python -m pytest tests/ -v"
        assert result["total_tokens"] == 150

    def test_planner_handles_invalid_json(self, tmp_path):
        """Planner should fall back to a default plan on malformed LLM output."""
        with patch("devrag.agent.planner.chat",
                   return_value=(_llm_msg("I cannot create a plan right now."), 20)):
            from devrag.agent.planner import planner_node

            result = planner_node(make_base_state(tmp_path))

        assert len(result["action_plan"]) >= 1
        assert result["files_to_edit"] == []


class TestTesterNode:
    def _run_tester(self, tmp_path, exit_code: int, output: str):
        from devrag.agent import tester

        proc = MagicMock()
        proc.returncode = exit_code
        proc.stdout = output
        proc.stderr = ""

        with patch.object(tester, "_ensure_pytest", return_value=True), \
             patch.object(tester, "_install_dependencies", return_value=(True, "")), \
             patch.object(tester.subprocess, "run", return_value=proc):
            state = make_base_state(tmp_path)
            state["test_command"] = "python -m pytest tests/ -v"
            state["code_changes"] = [{"tool": "str_replace_in_file", "file": "calculator.py"}]
            return tester.tester_node(state)

    def test_tester_passes_when_tests_pass(self, tmp_path):
        result = self._run_tester(tmp_path, exit_code=0, output="2 passed in 0.1s")
        assert result["test_passed"] is True
        assert "passed" in result["test_output"]

    def test_tester_fails_on_nonzero_exit(self, tmp_path):
        result = self._run_tester(tmp_path, exit_code=1, output="1 failed, 1 passed")
        assert result["test_passed"] is False

    def test_tester_detects_failed_text_despite_exit_zero(self, tmp_path):
        result = self._run_tester(tmp_path, exit_code=0, output="1 failed, 1 passed in 0.2s")
        assert result["test_passed"] is False


class TestCoderChangeTracking:
    def test_code_changes_shape(self):
        """code_changes entries carry the tool name and target file."""
        change = {"tool": "str_replace_in_file", "file": "src/calculator.py"}
        assert set(change) == {"tool", "file"}
