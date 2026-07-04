"""
test_planner.py — Tests for the planner node (LLM layer mocked).
"""
import sys
import os
import pathlib
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("GITHUB_TOKEN", "test_token")


MOCK_PLAN = {
    "action_plan": [
        "Step 1: Read src/calculator.py to understand the current implementation",
        "Step 2: Add None check at the start of calculate_total()",
        "Step 3: Run pytest to verify the fix",
    ],
    "files_to_edit": ["src/calculator.py"],
    "test_command": "pytest tests/ -v",
    "reasoning": "calculate_total() does not handle None values.",
}


def _llm_msg(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = []
    return msg


def _state(tmp_path) -> dict:
    return {
        "issue_number": 42,
        "issue_title": "calculate_total crashes on None input",
        "issue_body": "When passing None to calculate_total(), it raises AttributeError.",
        "repo_path": str(tmp_path),
        "action_plan": [],
        "files_to_edit": [],
    }


class TestPlannerNode:
    @patch("devrag.agent.planner.chat")
    def test_planner_returns_plan(self, mock_chat, tmp_path):
        mock_chat.return_value = (_llm_msg(json.dumps(MOCK_PLAN)), 120)

        from devrag.agent.planner import planner_node

        result = planner_node(_state(tmp_path))

        assert len(result["action_plan"]) == 3
        assert result["files_to_edit"] == ["src/calculator.py"]
        assert result["test_command"] == "pytest tests/ -v"

    @patch("devrag.agent.planner.chat")
    def test_planner_handles_malformed_json(self, mock_chat, tmp_path):
        mock_chat.return_value = (_llm_msg("This is not JSON at all"), 10)

        from devrag.agent.planner import planner_node

        # Should not raise — falls back to a default plan
        result = planner_node(_state(tmp_path))
        assert len(result["action_plan"]) > 0
        assert result["files_to_edit"] == []

    @patch("devrag.agent.planner.chat")
    def test_planner_strips_markdown_fences(self, mock_chat, tmp_path):
        fenced = "```json\n" + json.dumps(MOCK_PLAN) + "\n```"
        mock_chat.return_value = (_llm_msg(fenced), 90)

        from devrag.agent.planner import planner_node

        result = planner_node(_state(tmp_path))
        assert result["files_to_edit"] == ["src/calculator.py"]
