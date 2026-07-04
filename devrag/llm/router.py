"""
router.py — Complexity-based model routing for the DevRAG agent.

Estimates issue/task complexity from its text (ported from DevAgent) and maps
it to a current Claude model:

    TRIVIAL / SIMPLE  -> claude-haiku-4-5   (settings.model_fast)
    MEDIUM / COMPLEX  -> claude-sonnet-5    (settings.model_primary)
    ARCHITECT         -> settings.model_architect if set, else model_primary
"""
from __future__ import annotations

import re
from enum import Enum
from typing import List, Optional

from devrag import config


class TaskComplexity(Enum):
    TRIVIAL = "trivial"      # typo fix, config change, comment update
    SIMPLE = "simple"        # single function bug fix
    MEDIUM = "medium"        # multi-function fix, small feature
    COMPLEX = "complex"      # multi-file changes, new module
    ARCHITECT = "architect"  # system design, major refactoring


class TaskType(Enum):
    PLANNING = "planning"
    EXPLORING = "exploring"
    CODING = "coding"
    DEBUGGING = "debugging"
    REVIEWING = "reviewing"
    TESTING = "testing"


def pick_model(complexity: TaskComplexity, task_type: TaskType = TaskType.CODING) -> str:
    """Return the model id for a task."""
    if complexity in (TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE):
        # Planning benefits from the primary model even on simple tasks
        if task_type == TaskType.PLANNING:
            return config.MODEL_PRIMARY
        return config.MODEL_FAST
    if complexity == TaskComplexity.ARCHITECT and config.MODEL_ARCHITECT:
        return config.MODEL_ARCHITECT
    return config.MODEL_PRIMARY


def estimate_complexity(
    issue_title: str,
    issue_body: str,
    repo_structure: str = "",
    files_to_edit: Optional[List[str]] = None,
) -> TaskComplexity:
    """Heuristic complexity estimate from issue content (no LLM call)."""
    text = f"{issue_title}\n{issue_body}".lower()
    files = files_to_edit or []

    architect_patterns = [
        r"refactor\s+(entire|whole|all)",
        r"redesign",
        r"migrate\s+to",
        r"architecture",
        r"breaking\s+change",
        r"rewrite",
    ]
    for pattern in architect_patterns:
        if re.search(pattern, text):
            return TaskComplexity.ARCHITECT

    complex_patterns = [
        r"add\s+(new\s+)?(feature|endpoint|api|module)",
        r"implement",
        r"create\s+(new\s+)?(class|service|component)",
        r"integrate",
        r"multiple\s+files",
    ]
    for pattern in complex_patterns:
        if re.search(pattern, text):
            return TaskComplexity.COMPLEX

    if len(files) > 3:
        return TaskComplexity.COMPLEX
    if len(files) > 1:
        return TaskComplexity.MEDIUM

    medium_patterns = [
        r"add\s+(method|function|handler)",
        r"update\s+(logic|behavior)",
        r"fix\s+.{0,20}(and|also)",
    ]
    for pattern in medium_patterns:
        if re.search(pattern, text):
            return TaskComplexity.MEDIUM

    trivial_patterns = [
        r"typo",
        r"spelling",
        r"comment",
        r"readme",
        r"documentation",
        r"version\s+bump",
        r"update\s+dependency",
    ]
    for pattern in trivial_patterns:
        if re.search(pattern, text):
            return TaskComplexity.TRIVIAL

    return TaskComplexity.SIMPLE
