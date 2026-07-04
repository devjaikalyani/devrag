"""
hierarchical_planner.py — Break complex issues into manageable sub-tasks.

For complex issues that require multiple files or features:
1. Decompose into atomic sub-tasks
2. Identify dependencies between sub-tasks
3. Generate execution order (topological sort)
4. Track progress through sub-tasks

This enables the agent to tackle issues like:
- "Add user authentication with JWT"
- "Refactor database layer to use async"
- "Implement REST API for user management"
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, Set, Any
from collections import defaultdict

from rich.console import Console
from rich.tree import Tree

from .state import AgentState
from devrag.llm.client import chat
from devrag.llm.router import TaskComplexity, estimate_complexity

console = Console()


class SubTaskStatus(Enum):
    """Status of a sub-task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SubTaskType(Enum):
    """Type of sub-task."""
    CREATE_FILE = "create_file"
    MODIFY_FILE = "modify_file"
    ADD_DEPENDENCY = "add_dependency"
    WRITE_TEST = "write_test"
    UPDATE_CONFIG = "update_config"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"


@dataclass
class SubTask:
    """A single atomic sub-task."""
    id: str
    title: str
    description: str
    task_type: SubTaskType
    files_to_create: List[str] = field(default_factory=list)
    files_to_modify: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)  # Sub-task IDs
    test_criteria: str = ""
    status: SubTaskStatus = SubTaskStatus.PENDING
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type.value,
            "files_to_create": self.files_to_create,
            "files_to_modify": self.files_to_modify,
            "depends_on": self.depends_on,
            "test_criteria": self.test_criteria,
            "status": self.status.value,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SubTask":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            task_type=SubTaskType(data.get("task_type", "modify_file")),
            files_to_create=data.get("files_to_create", []),
            files_to_modify=data.get("files_to_modify", []),
            depends_on=data.get("depends_on", []),
            test_criteria=data.get("test_criteria", ""),
            status=SubTaskStatus(data.get("status", "pending")),
        )


@dataclass
class TaskPlan:
    """Complete hierarchical plan for an issue."""
    issue_id: int
    issue_title: str
    complexity: TaskComplexity
    summary: str
    sub_tasks: List[SubTask] = field(default_factory=list)
    execution_order: List[str] = field(default_factory=list)  # Sub-task IDs in order
    
    def get_ready_tasks(self) -> List[SubTask]:
        """Get sub-tasks that are ready to execute (dependencies completed)."""
        completed = {st.id for st in self.sub_tasks if st.status == SubTaskStatus.COMPLETED}
        ready = []
        for st in self.sub_tasks:
            if st.status != SubTaskStatus.PENDING:
                continue
            deps_met = all(dep in completed for dep in st.depends_on)
            if deps_met:
                ready.append(st)
        return ready
    
    def get_progress(self) -> Dict[str, int]:
        """Get progress statistics."""
        stats = defaultdict(int)
        for st in self.sub_tasks:
            stats[st.status.value] += 1
        stats["total"] = len(self.sub_tasks)
        return dict(stats)
    
    def to_dict(self) -> Dict:
        return {
            "issue_id": self.issue_id,
            "issue_title": self.issue_title,
            "complexity": self.complexity.value,
            "summary": self.summary,
            "sub_tasks": [st.to_dict() for st in self.sub_tasks],
            "execution_order": self.execution_order,
        }
    
    def print_tree(self):
        """Print task plan as a tree."""
        tree = Tree(f"[bold]{self.issue_title}[/bold] ({self.complexity.value})")
        for st in self.sub_tasks:
            status_icon = {
                SubTaskStatus.PENDING: "PENDING",
                SubTaskStatus.IN_PROGRESS: "RUNNING",
                SubTaskStatus.COMPLETED: "OK",
                SubTaskStatus.FAILED: "FAIL",
                SubTaskStatus.SKIPPED: "SKIP",
            }.get(st.status, "?")
            
            branch = tree.add(f"{status_icon} [{st.task_type.value}] {st.title}")
            if st.files_to_create:
                branch.add(f"[green]Create:[/green] {', '.join(st.files_to_create)}")
            if st.files_to_modify:
                branch.add(f"[yellow]Modify:[/yellow] {', '.join(st.files_to_modify)}")
            if st.depends_on:
                branch.add(f"[dim]Depends on:[/dim] {', '.join(st.depends_on)}")
        
        console.print(tree)


_DECOMPOSE_SYSTEM = """\
You are a senior software architect. Given a GitHub issue and repository structure, \
decompose it into atomic, executable sub-tasks.

Output ONLY valid JSON (no markdown fences):
{
  "summary": "Brief description of what needs to be done",
  "sub_tasks": [
    {
      "id": "task-1",
      "title": "Short task title",
      "description": "Detailed description of what to do",
      "task_type": "create_file|modify_file|add_dependency|write_test|update_config|refactor|documentation",
      "files_to_create": ["path/to/new/file.py"],
      "files_to_modify": ["path/to/existing/file.py"],
      "depends_on": [],
      "test_criteria": "How to verify this task is complete"
    },
    {
      "id": "task-2",
      "title": "Another task",
      "description": "...",
      "task_type": "modify_file",
      "files_to_create": [],
      "files_to_modify": ["src/main.py"],
      "depends_on": ["task-1"],
      "test_criteria": "..."
    }
  ]
}

## CRITICAL Rules
1. **ONLY USE PATHS FROM THE PROVIDED REPOSITORY STRUCTURE** - Never guess or invent file paths
2. For files_to_modify, the path MUST exist in the "Repository Structure" section below
3. For files_to_create, place them in directories that EXIST in the repo structure
4. If a standard folder like models/ or services/ doesn't exist, DON'T CREATE FILES THERE
5. Study the repo structure carefully - use the ACTUAL folder names (e.g., "routers" not "routes")
6. Each sub-task should be atomic - completable in one coding session
7. Order tasks by dependencies - a task can only depend on earlier tasks
8. Use descriptive IDs like "modify-activities-router", "add-filter-ui"
9. Maximum 10 sub-tasks (break into phases if needed)
10. For simple bugs, return a single sub-task

## Common Mistakes to Avoid
- FAIL Inventing paths like "models/user.py" when no models/ folder exists
- FAIL Using "routes/" when the repo uses "routers/"
- FAIL Creating deeply nested folders that don't exist
- ok Study the tree structure and match EXACTLY"""


def decompose_issue(
    issue_number: int,
    issue_title: str,
    issue_body: str,
    repo_structure: str,
    existing_files: List[str] = None,
) -> TaskPlan:
    """
    Decompose a GitHub issue into sub-tasks.
    
    Args:
        issue_number: GitHub issue number
        issue_title: Issue title
        issue_body: Issue body/description
        repo_structure: Tree structure of repository
        existing_files: List of relevant existing files
        
    Returns:
        TaskPlan with sub-tasks and execution order
    """
    console.print("[bold cyan]Decomposing issue into sub-tasks...[/bold cyan]")
    
    # Estimate complexity first
    complexity = estimate_complexity(
        issue_title, 
        issue_body, 
        repo_structure,
        existing_files or [],
    )
    console.print(f"  [dim]Estimated complexity: {complexity.value}[/dim]")
    
    # For trivial/simple issues, create a single sub-task
    if complexity in (TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE):
        return _create_simple_plan(issue_number, issue_title, issue_body, complexity)
    
    # Use LLM to decompose complex issues
    messages = [
        {"role": "system", "content": _DECOMPOSE_SYSTEM},
        {"role": "user", "content": 
            f"## Issue #{issue_number}: {issue_title}\n\n"
            f"{issue_body}\n\n"
            f"## Repository Structure\n{repo_structure[:3000]}\n\n"
            f"## Existing Files\n{chr(10).join(existing_files or [])}"
        },
    ]
    
    msg, tokens = chat(messages, max_tokens=2048, temperature=0.0, json_mode=True)
    response = msg.content or ""
    
    try:
        # Parse JSON response
        raw = response.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(raw)
    except json.JSONDecodeError:
        console.print(f"[yellow]Failed to parse decomposition, using fallback[/yellow]")
        return _create_simple_plan(issue_number, issue_title, issue_body, complexity)
    
    # Build TaskPlan
    sub_tasks = []
    for st_data in data.get("sub_tasks", []):
        try:
            sub_task = SubTask.from_dict(st_data)
            sub_tasks.append(sub_task)
        except Exception as e:
            console.print(f"[yellow]Skipping invalid sub-task: {e}[/yellow]")
    
    if not sub_tasks:
        return _create_simple_plan(issue_number, issue_title, issue_body, complexity)
    
    # Generate execution order (topological sort)
    execution_order = _topological_sort(sub_tasks)
    
    plan = TaskPlan(
        issue_id=issue_number,
        issue_title=issue_title,
        complexity=complexity,
        summary=data.get("summary", issue_title),
        sub_tasks=sub_tasks,
        execution_order=execution_order,
    )
    
    console.print(f"  [dim]Created plan with {len(sub_tasks)} sub-tasks[/dim]")
    plan.print_tree()
    
    return plan


def _create_simple_plan(
    issue_number: int,
    issue_title: str,
    issue_body: str,
    complexity: TaskComplexity,
) -> TaskPlan:
    """Create a simple single-task plan for trivial/simple issues."""
    sub_task = SubTask(
        id="fix-issue",
        title=issue_title,
        description=issue_body,
        task_type=SubTaskType.MODIFY_FILE,
        test_criteria="All tests pass",
    )
    
    return TaskPlan(
        issue_id=issue_number,
        issue_title=issue_title,
        complexity=complexity,
        summary=f"Fix: {issue_title}",
        sub_tasks=[sub_task],
        execution_order=["fix-issue"],
    )


def _topological_sort(sub_tasks: List[SubTask]) -> List[str]:
    """
    Sort sub-tasks by dependencies (Kahn's algorithm).
    
    Returns list of sub-task IDs in execution order.
    """
    # Build adjacency list and in-degree count
    graph = defaultdict(list)
    in_degree = defaultdict(int)
    task_ids = {st.id for st in sub_tasks}
    
    for st in sub_tasks:
        in_degree[st.id] = 0
    
    for st in sub_tasks:
        for dep in st.depends_on:
            if dep in task_ids:
                graph[dep].append(st.id)
                in_degree[st.id] += 1
    
    # Start with tasks that have no dependencies
    queue = [st.id for st in sub_tasks if in_degree[st.id] == 0]
    result = []
    
    while queue:
        node = queue.pop(0)
        result.append(node)
        
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    # Check for cycles
    if len(result) != len(sub_tasks):
        console.print("[yellow]Warning: Circular dependencies detected, using original order[/yellow]")
        return [st.id for st in sub_tasks]
    
    return result


def validate_paths(sub_tasks: List[SubTask], repo_root: str) -> List[SubTask]:
    """
    Validate that files_to_modify exist and files_to_create are in valid directories.
    
    This catches hallucinated paths before execution.
    """
    validated = []
    
    for st in sub_tasks:
        valid = True
        issues = []
        
        # Check files to modify exist
        for file_path in st.files_to_modify:
            full_path = os.path.join(repo_root, file_path)
            if not os.path.exists(full_path):
                issues.append(f"File to modify doesn't exist: {file_path}")
                valid = False
        
        # Check files to create are in valid directories
        for file_path in st.files_to_create:
            dir_path = os.path.dirname(file_path)
            if dir_path:
                full_dir = os.path.join(repo_root, dir_path)
                if not os.path.exists(full_dir):
                    issues.append(f"Directory doesn't exist for new file: {dir_path}")
                    valid = False
        
        if valid:
            validated.append(st)
        else:
            console.print(f"[yellow]Skipping invalid sub-task '{st.id}':[/yellow]")
            for issue in issues:
                console.print(f"  [dim]- {issue}[/dim]")
            # Mark as skipped
            st.status = SubTaskStatus.SKIPPED
            validated.append(st)
    
    return validated


def decompose_node(state: AgentState) -> dict:
    """
    LangGraph node: Decompose complex issue into sub-tasks.
    
    This node is called for COMPLEX and ARCHITECT level issues.
    """
    console.print("[bold cyan]Decomposing complex issue...[/bold cyan]")
    
    plan = decompose_issue(
        issue_number=state["issue_number"],
        issue_title=state["issue_title"],
        issue_body=state["issue_body"],
        repo_structure=state.get("repo_map", ""),
        existing_files=state.get("files_to_edit", []),
    )
    
    # Validate paths against actual repo structure
    repo_root = state.get("repo_path", "")
    if repo_root and os.path.exists(repo_root):
        plan.sub_tasks = validate_paths(plan.sub_tasks, repo_root)
        # Update execution order to skip invalid tasks
        valid_ids = {st.id for st in plan.sub_tasks if st.status != SubTaskStatus.SKIPPED}
        plan.execution_order = [tid for tid in plan.execution_order if tid in valid_ids]
    
    return {
        "task_plan": plan.to_dict(),
        "sub_tasks": [st.to_dict() for st in plan.sub_tasks],
        "current_sub_task": plan.execution_order[0] if plan.execution_order else None,
        "execution_order": plan.execution_order,
        "complexity": plan.complexity.value,
        "total_tokens": state.get("total_tokens", 0),
    }


def get_next_subtask(state: AgentState) -> Optional[SubTask]:
    """Get the next sub-task to execute based on current progress."""
    sub_tasks_data = state.get("sub_tasks", [])
    execution_order = state.get("execution_order", [])
    
    if not sub_tasks_data or not execution_order:
        return None
    
    # Rebuild sub-tasks
    sub_tasks = [SubTask.from_dict(st) for st in sub_tasks_data]
    task_map = {st.id: st for st in sub_tasks}
    
    # Find first pending task in execution order
    completed = {st.id for st in sub_tasks if st.status == SubTaskStatus.COMPLETED}
    
    for task_id in execution_order:
        task = task_map.get(task_id)
        if not task:
            continue
        if task.status == SubTaskStatus.PENDING:
            # Check dependencies
            deps_met = all(dep in completed for dep in task.depends_on)
            if deps_met:
                return task
    
    return None


def mark_subtask_complete(state: AgentState, task_id: str, success: bool, error: str = None) -> dict:
    """Mark a sub-task as completed or failed."""
    sub_tasks_data = state.get("sub_tasks", [])
    
    for st in sub_tasks_data:
        if st["id"] == task_id:
            st["status"] = "completed" if success else "failed"
            if error:
                st["error"] = error
            break
    
    return {"sub_tasks": sub_tasks_data}
