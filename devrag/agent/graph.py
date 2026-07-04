"""
graph.py — LangGraph StateGraph definition (Enhanced).

Node topology for simple issues:
  plan → explore → code → test ──(pass)──→ review → open_pr → END
                              └──(fail)──→ debug ──→ test (loop)
                              └──(max_retries)──→ END(failed)

Node topology for complex issues:
  analyze → decompose → [for each subtask]:
    explore → code → test → (loop until done) → review → open_pr → END

New capabilities:
- Complexity-based routing (simple vs complex issues)
- Hierarchical task decomposition
- Self-review before PR
- RAG-based code search
"""
from __future__ import annotations

from typing import Literal
from langgraph.graph import StateGraph, END

from devrag.agent.state import AgentState
from devrag.agent.planner import planner_node
from devrag.agent.explorer import explorer_node
from devrag.agent.coder import coder_node
from devrag.agent.tester import tester_node
from devrag.agent.debugger import debugger_node
from devrag.agent.pr_opener import pr_opener_node
from devrag.agent.reviewer import review_node
from devrag.agent.hierarchical_planner import decompose_node
from devrag.llm.router import estimate_complexity, TaskComplexity
from devrag import config


# ─────────────────────────────────────────────────────────────────────────────
# Conditional routing
# ─────────────────────────────────────────────────────────────────────────────

def route_by_complexity(state: AgentState) -> str:
    """
    Route based on issue complexity.
    
    Returns:
      "decompose" — complex issue, needs hierarchical planning
      "explore"   — simple issue, go straight to exploration
    """
    complexity = state.get("complexity")
    
    if complexity is None:
        # Estimate complexity from issue
        complexity = estimate_complexity(
            state.get("issue_title", ""),
            state.get("issue_body", ""),
            state.get("repo_map", ""),
            state.get("files_to_edit", []),
        )
        # Store for later use
        state["complexity"] = complexity.value
    
    if complexity in (TaskComplexity.COMPLEX, TaskComplexity.ARCHITECT):
        return "decompose"
    return "explore"


def route_after_test(state: AgentState) -> str:
    """
    Conditional edge from the 'test' node.

    Returns:
      "review"   — all tests pass → run self-review
      "debug"    — tests failed, retries remaining → fix and retry
      "failed"   — max retries exhausted → give up, surface error
    """
    if state["test_passed"]:
        return "review"
    if state.get("retry_count", 0) >= config.MAX_RETRIES:
        return "failed"
    return "debug"


def route_after_review(state: AgentState) -> str:
    """
    Conditional edge from the 'review' node.

    Returns:
      "done"     — no-PR run finished, or review loop cap reached on a no-PR run
      "open_pr"  — review passed (or loop cap reached), create PR
      "code"     — review found blocking issues, fix them (max 2 review cycles)
    """
    review_ok = state.get("review_passed", True)
    blocking_issues = state.get("review_issues") or []
    has_blockers = not review_ok and any("ERROR" in str(i) for i in blocking_issues)

    # Cap review->code cycles: tests already pass at this point, so after two
    # attempts ship what we have instead of looping forever.
    if has_blockers and state.get("review_count", 0) < 2:
        return "code"

    # Honor the no-PR flag (local runs, task mode, dry runs)
    if state.get("no_pr"):
        return "done"

    return "open_pr"


def route_after_decompose(state: AgentState) -> str:
    """
    After decomposition, always proceed to explore.
    """
    return "explore"


# ─────────────────────────────────────────────────────────────────────────────
# Graph construction
# ─────────────────────────────────────────────────────────────────────────────

def build_graph(enhanced: bool = True):
    """
    Build and compile the DevAgent LangGraph.
    
    Args:
        enhanced: If True, use enhanced graph with complexity routing and review.
                  If False, use simple linear graph for backward compatibility.
    """
    g = StateGraph(AgentState)

    # Register nodes
    g.add_node("plan",      planner_node)
    g.add_node("explore",   explorer_node)
    g.add_node("code",      coder_node)
    g.add_node("test",      tester_node)
    g.add_node("debug",     debugger_node)
    g.add_node("open_pr",   pr_opener_node)
    
    if enhanced:
        g.add_node("decompose", decompose_node)
        g.add_node("review",    review_node)
    
        # Entry point with complexity routing
        g.set_entry_point("plan")
        
        # After plan, route by complexity
        g.add_conditional_edges(
            "plan",
            route_by_complexity,
            {
                "decompose": "decompose",
                "explore": "explore",
            },
        )
        
        # Decompose always leads to explore
        g.add_edge("decompose", "explore")
        
        # Standard flow
        g.add_edge("explore", "code")
        g.add_edge("code",    "test")
        g.add_edge("debug",   "test")
        
        # Test result routing (now goes to review instead of open_pr)
        g.add_conditional_edges(
            "test",
            route_after_test,
            {
                "review": "review",
                "debug":  "debug",
                "failed": END,
            },
        )
        
        # Review result routing
        g.add_conditional_edges(
            "review",
            route_after_review,
            {
                "open_pr": "open_pr",
                "code":    "code",
                "done":    END,
            },
        )
        
        g.add_edge("open_pr", END)
    
    else:
        # Simple linear graph (original behavior)
        g.set_entry_point("plan")
        g.add_edge("plan",    "explore")
        g.add_edge("explore", "code")
        g.add_edge("code",    "test")
        g.add_edge("debug",   "test")
        g.add_edge("open_pr", END)
        
        g.add_conditional_edges(
            "test",
            lambda state: "open_pr" if state["test_passed"] 
                          else ("debug" if state.get("retry_count", 0) < config.MAX_RETRIES 
                                else "failed"),
            {
                "open_pr": "open_pr",
                "debug":   "debug",
                "failed":  END,
            },
        )

    return g.compile()


def build_simple_graph():
    """Build simple graph without enhanced features (backward compatible)."""
    return build_graph(enhanced=False)


# Singleton compiled graph — import this in main.py
# Use enhanced graph by default
app = build_graph(enhanced=True)

# Also export simple graph for testing
simple_app = build_graph(enhanced=False)
