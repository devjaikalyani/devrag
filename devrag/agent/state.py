from __future__ import annotations
from typing import TypedDict, Optional, List, Dict, Any

class AgentState(TypedDict):
    """
    Shared state passed between all LangGraph nodes.
    
    Enhanced to support:
    - Hierarchical task decomposition
    - Complexity-based routing
    - Self-review before PR
    - Multi-language support
    """
    # ── Input ─────────────────────────────────────────────────────────────────
    issue_url:      str
    issue_number:   int
    issue_title:    str
    issue_body:     str
    repo_owner:     str
    repo_name:      str
    repo_path:      str
    branch_name:    str
    
    # ── Planning ──────────────────────────────────────────────────────────────
    action_plan:    list
    files_to_edit:  list
    repo_map:       str
    
    # ── Hierarchical Planning (New) ───────────────────────────────────────────
    complexity:         Optional[str]           # trivial, simple, medium, complex, architect
    task_plan:          Optional[Dict[str, Any]]  # Full hierarchical plan
    sub_tasks:          Optional[List[Dict]]    # List of sub-task dicts
    current_sub_task:   Optional[str]           # ID of current sub-task
    execution_order:    Optional[List[str]]     # Sub-task IDs in order
    
    # ── Execution ─────────────────────────────────────────────────────────────
    messages:       list
    code_changes:   list
    
    # ── Testing ───────────────────────────────────────────────────────────────
    test_command:   str
    test_output:    str
    test_passed:    bool
    retry_count:    int
    max_retries:    int
    
    # ── Review (New) ──────────────────────────────────────────────────────────
    review_passed:      Optional[bool]
    review_issues:      Optional[List[str]]     # List of issue strings
    review_count:       Optional[int]           # Review iterations so far (loop cap)
    pr_description:     Optional[str]           # Generated PR description

    # ── Output ────────────────────────────────────────────────────────────────
    no_pr:          Optional[bool]              # Skip PR creation (local/task runs)
    pr_url:         Optional[str]
    pr_number:      Optional[int]
    error:          Optional[str]
    total_tokens:   int
