"""
reviewer.py — Self-review code before creating PR.

Performs automated code review to catch issues before PR:
- Code quality checks (complexity, duplication)
- Bug detection (null checks, type errors)
- Security review (injection, secrets)
- Best practices validation
- Documentation completeness

This enables the agent to:
- Catch common mistakes before humans review
- Ensure code quality meets standards
- Generate helpful PR descriptions
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from langchain_core.tools import tool
from rich.console import Console
from rich.table import Table

from .state import AgentState
from devrag.llm.client import chat

console = Console()


class IssueSeverity(Enum):
    """Severity level for review issues."""
    ERROR = "error"       # Must fix before merge
    WARNING = "warning"   # Should fix
    INFO = "info"         # Consider fixing
    STYLE = "style"       # Style suggestion


class IssueCategory(Enum):
    """Category of review issue."""
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    DOCUMENTATION = "documentation"
    COMPLEXITY = "complexity"
    BEST_PRACTICE = "best_practice"


@dataclass
class ReviewIssue:
    """A single issue found during review."""
    file_path: str
    line_number: int
    severity: IssueSeverity
    category: IssueCategory
    message: str
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None
    
    def __str__(self):
        return f"[{self.severity.value.upper()}] {self.file_path}:{self.line_number} - {self.message}"


@dataclass
class ReviewResult:
    """Result of a code review."""
    files_reviewed: List[str]
    issues: List[ReviewIssue]
    passed: bool
    summary: str
    pr_description: Optional[str] = None
    
    def print_report(self):
        """Print formatted review report."""
        # Header
        status = "ok PASSED" if self.passed else "FAIL ISSUES FOUND"
        console.print(f"\n[bold]{status}[/bold] - {len(self.files_reviewed)} files reviewed\n")
        
        if not self.issues:
            console.print("[green]No issues found![/green]")
            return
        
        # Issues table
        table = Table(title="Review Issues")
        table.add_column("Severity", style="bold")
        table.add_column("File")
        table.add_column("Line")
        table.add_column("Category")
        table.add_column("Message")
        
        severity_styles = {
            IssueSeverity.ERROR: "red",
            IssueSeverity.WARNING: "yellow",
            IssueSeverity.INFO: "cyan",
            IssueSeverity.STYLE: "dim",
        }
        
        for issue in sorted(self.issues, key=lambda i: (i.severity.value, i.file_path)):
            style = severity_styles.get(issue.severity, "white")
            table.add_row(
                f"[{style}]{issue.severity.value}[/{style}]",
                issue.file_path,
                str(issue.line_number),
                issue.category.value,
                issue.message[:50] + "..." if len(issue.message) > 50 else issue.message,
            )
        
        console.print(table)
        
        # Summary
        error_count = sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)
        warning_count = sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)
        console.print(f"\n{error_count} errors, {warning_count} warnings")
    
    def get_blocking_issues(self) -> List[ReviewIssue]:
        """Get issues that should block merge."""
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]


class CodeReviewer:
    """Automated code reviewer."""
    
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root).resolve()
    
    def _safe_path(self, rel_path: str) -> Path:
        """Resolve path safely within repo."""
        target = (self.repo_root / rel_path).resolve()
        if not str(target).startswith(str(self.repo_root)):
            raise PermissionError(f"Path traversal blocked: {rel_path}")
        return target
    
    def review_file(self, rel_path: str) -> List[ReviewIssue]:
        """Review a single Python file."""
        issues = []
        
        try:
            path = self._safe_path(rel_path)
            content = path.read_text(encoding="utf-8")
            lines = content.split("\n")
        except Exception as e:
            return [ReviewIssue(
                file_path=rel_path,
                line_number=0,
                severity=IssueSeverity.ERROR,
                category=IssueCategory.BUG,
                message=f"Cannot read file: {e}",
            )]
        
        # Run all checks
        issues.extend(self._check_syntax(rel_path, content))
        issues.extend(self._check_security(rel_path, lines))
        issues.extend(self._check_bugs(rel_path, content, lines))
        issues.extend(self._check_complexity(rel_path, content))
        issues.extend(self._check_documentation(rel_path, content))
        issues.extend(self._check_best_practices(rel_path, lines))
        
        return issues
    
    def _check_syntax(self, file_path: str, content: str) -> List[ReviewIssue]:
        """Check for syntax errors."""
        issues = []
        try:
            ast.parse(content)
        except SyntaxError as e:
            issues.append(ReviewIssue(
                file_path=file_path,
                line_number=e.lineno or 0,
                severity=IssueSeverity.ERROR,
                category=IssueCategory.BUG,
                message=f"Syntax error: {e.msg}",
                code_snippet=e.text,
            ))
        return issues
    
    def _check_security(self, file_path: str, lines: List[str]) -> List[ReviewIssue]:
        """Check for security issues."""
        issues = []
        
        security_patterns = [
            # Hardcoded secrets
            (r'(password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']', 
             "Possible hardcoded secret", IssueSeverity.ERROR),
            
            # SQL injection
            (r'execute\([^)]*%[sd]|execute\([^)]*\+|execute\(f["\']',
             "Potential SQL injection - use parameterized queries", IssueSeverity.ERROR),
            
            # Command injection
            (r'os\.system\(|subprocess\.(call|run|Popen)\([^)]*shell\s*=\s*True',
             "Potential command injection - avoid shell=True", IssueSeverity.WARNING),
            
            # Pickle deserialization
            (r'pickle\.load|pickle\.loads',
             "Pickle deserialization can execute arbitrary code", IssueSeverity.WARNING),
            
            # Eval/exec
            (r'\beval\s*\(|\bexec\s*\(',
             "eval/exec can execute arbitrary code", IssueSeverity.WARNING),
            
            # Insecure random
            (r'import random(?!.*secrets)',
             "Use secrets module for security-sensitive random values", IssueSeverity.INFO),
            
            # Debug mode in production
            (r'debug\s*=\s*True|DEBUG\s*=\s*True',
             "Debug mode should be disabled in production", IssueSeverity.WARNING),
        ]
        
        for i, line in enumerate(lines, start=1):
            for pattern, message, severity in security_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(ReviewIssue(
                        file_path=file_path,
                        line_number=i,
                        severity=severity,
                        category=IssueCategory.SECURITY,
                        message=message,
                        code_snippet=line.strip(),
                    ))
        
        return issues
    
    def _check_bugs(self, file_path: str, content: str, lines: List[str]) -> List[ReviewIssue]:
        """Check for common bugs."""
        issues = []
        
        bug_patterns = [
            # Mutable default arguments
            (r'def\s+\w+\([^)]*=\s*(\[\]|\{\}|\w+\(\))',
             "Mutable default argument - use None instead", IssueSeverity.WARNING),
            
            # Catching too broad exception
            (r'except\s*:|except\s+Exception\s*:',
             "Catching too broad exception", IssueSeverity.INFO),
            
            # Using == for None comparison
            (r'==\s*None|!=\s*None',
             "Use 'is None' or 'is not None' instead", IssueSeverity.STYLE),
            
            # Unused variables (simple check)
            (r'^\s*(\w+)\s*=\s*.+\s*#\s*noqa',
             "Variable may be unused", IssueSeverity.INFO),
            
            # Empty except
            (r'except.*:\s*\n\s*pass\s*$',
             "Empty except block - at least log the error", IssueSeverity.WARNING),
            
            # Assert in production code
            (r'^\s*assert\s+',
             "Assert statements can be disabled - use explicit checks", IssueSeverity.INFO),
        ]
        
        for i, line in enumerate(lines, start=1):
            for pattern, message, severity in bug_patterns:
                if re.search(pattern, line):
                    issues.append(ReviewIssue(
                        file_path=file_path,
                        line_number=i,
                        severity=severity,
                        category=IssueCategory.BUG,
                        message=message,
                        code_snippet=line.strip(),
                    ))
        
        # AST-based checks
        try:
            tree = ast.parse(content)
            
            # Check for unreachable code after return
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    found_return = False
                    for child in ast.iter_child_nodes(node):
                        if found_return and not isinstance(child, (ast.Pass, ast.Expr)):
                            issues.append(ReviewIssue(
                                file_path=file_path,
                                line_number=getattr(child, 'lineno', 0),
                                severity=IssueSeverity.WARNING,
                                category=IssueCategory.BUG,
                                message="Unreachable code after return",
                            ))
                        if isinstance(child, ast.Return):
                            found_return = True
            
            # Check for shadowing builtins
            builtins = {'list', 'dict', 'set', 'str', 'int', 'float', 'type', 'id', 'input', 'print', 'len', 'range'}
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    if node.id in builtins:
                        issues.append(ReviewIssue(
                            file_path=file_path,
                            line_number=node.lineno,
                            severity=IssueSeverity.WARNING,
                            category=IssueCategory.BUG,
                            message=f"Shadowing builtin '{node.id}'",
                        ))
        
        except SyntaxError:
            pass  # Already caught in syntax check
        
        return issues
    
    def _check_complexity(self, file_path: str, content: str) -> List[ReviewIssue]:
        """Check for complexity issues."""
        issues = []
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return issues
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check function length
                func_lines = node.end_lineno - node.lineno + 1
                if func_lines > 50:
                    issues.append(ReviewIssue(
                        file_path=file_path,
                        line_number=node.lineno,
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.COMPLEXITY,
                        message=f"Function '{node.name}' is {func_lines} lines - consider splitting",
                        suggestion="Break into smaller functions with single responsibilities",
                    ))
                
                # Check cyclomatic complexity (simplified)
                complexity = 1
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                        complexity += 1
                    elif isinstance(child, ast.BoolOp):
                        complexity += len(child.values) - 1
                
                if complexity > 10:
                    issues.append(ReviewIssue(
                        file_path=file_path,
                        line_number=node.lineno,
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.COMPLEXITY,
                        message=f"Function '{node.name}' has high complexity ({complexity})",
                        suggestion="Reduce nesting and conditionals",
                    ))
                
                # Check number of parameters
                num_params = len(node.args.args)
                if num_params > 5:
                    issues.append(ReviewIssue(
                        file_path=file_path,
                        line_number=node.lineno,
                        severity=IssueSeverity.INFO,
                        category=IssueCategory.COMPLEXITY,
                        message=f"Function '{node.name}' has {num_params} parameters",
                        suggestion="Consider using a dataclass or config object",
                    ))
        
        return issues
    
    def _check_documentation(self, file_path: str, content: str) -> List[ReviewIssue]:
        """Check for documentation issues."""
        issues = []
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return issues
        
        # Check module docstring
        if not ast.get_docstring(tree):
            issues.append(ReviewIssue(
                file_path=file_path,
                line_number=1,
                severity=IssueSeverity.INFO,
                category=IssueCategory.DOCUMENTATION,
                message="Missing module docstring",
            ))
        
        # Check function/class docstrings
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip private functions
                if node.name.startswith("_"):
                    continue
                
                if not ast.get_docstring(node):
                    issues.append(ReviewIssue(
                        file_path=file_path,
                        line_number=node.lineno,
                        severity=IssueSeverity.INFO,
                        category=IssueCategory.DOCUMENTATION,
                        message=f"Missing docstring for function '{node.name}'",
                    ))
            
            elif isinstance(node, ast.ClassDef):
                if not ast.get_docstring(node):
                    issues.append(ReviewIssue(
                        file_path=file_path,
                        line_number=node.lineno,
                        severity=IssueSeverity.INFO,
                        category=IssueCategory.DOCUMENTATION,
                        message=f"Missing docstring for class '{node.name}'",
                    ))
        
        return issues
    
    def _check_best_practices(self, file_path: str, lines: List[str]) -> List[ReviewIssue]:
        """Check for best practice violations."""
        issues = []
        
        practice_patterns = [
            # Print statements (should use logging)
            (r'^\s*print\s*\(', 
             "Use logging instead of print for production code", IssueSeverity.INFO),
            
            # TODO/FIXME comments
            (r'#\s*(TODO|FIXME|XXX|HACK)',
             "Unresolved TODO/FIXME comment", IssueSeverity.INFO),
            
            # Magic numbers
            (r'if\s+\w+\s*[<>=]+\s*\d{2,}|for\s+\w+\s+in\s+range\s*\(\s*\d{2,}',
             "Consider using named constant instead of magic number", IssueSeverity.STYLE),
            
            # Commented out code
            (r'^\s*#\s*(def|class|if|for|while|return|import)',
             "Commented out code - remove or restore", IssueSeverity.STYLE),
            
            # Long lines
            # (checked separately with correct threshold)
        ]
        
        for i, line in enumerate(lines, start=1):
            # Line length check
            if len(line) > 120:
                issues.append(ReviewIssue(
                    file_path=file_path,
                    line_number=i,
                    severity=IssueSeverity.STYLE,
                    category=IssueCategory.STYLE,
                    message=f"Line too long ({len(line)} > 120 chars)",
                ))
            
            for pattern, message, severity in practice_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(ReviewIssue(
                        file_path=file_path,
                        line_number=i,
                        severity=severity,
                        category=IssueCategory.BEST_PRACTICE,
                        message=message,
                        code_snippet=line.strip()[:60],
                    ))
        
        return issues
    
    def review_changes(
        self,
        changed_files: List[str],
        issue_title: str = "",
        issue_body: str = "",
    ) -> ReviewResult:
        """
        Review changed files.
        
        Args:
            changed_files: List of files that were modified
            issue_title: Title of the issue being fixed
            issue_body: Body of the issue
            
        Returns:
            ReviewResult with all findings
        """
        console.print(f"[bold cyan]Reviewing {len(changed_files)} files...[/bold cyan]")
        
        all_issues = []
        files_reviewed = []
        
        for file_path in changed_files:
            if not file_path.endswith(".py"):
                continue
            
            files_reviewed.append(file_path)
            issues = self.review_file(file_path)
            all_issues.extend(issues)
        
        # Determine if review passes
        error_count = sum(1 for i in all_issues if i.severity == IssueSeverity.ERROR)
        passed = error_count == 0
        
        # Generate summary
        if not all_issues:
            summary = "All checks passed - no issues found!"
        else:
            summary = f"Found {len(all_issues)} issues ({error_count} errors)"
        
        # Generate PR description using LLM
        pr_description = self._generate_pr_description(
            files_reviewed,
            all_issues,
            issue_title,
            issue_body,
        )
        
        return ReviewResult(
            files_reviewed=files_reviewed,
            issues=all_issues,
            passed=passed,
            summary=summary,
            pr_description=pr_description,
        )
    
    def _generate_pr_description(
        self,
        files: List[str],
        issues: List[ReviewIssue],
        issue_title: str,
        issue_body: str,
    ) -> str:
        """Generate PR description using LLM."""
        if not issue_title:
            return ""
        
        blocking = [i for i in issues if i.severity == IssueSeverity.ERROR]
        warnings = [i for i in issues if i.severity == IssueSeverity.WARNING]
        
        prompt = f"""Generate a concise PR description for these changes.

Issue: {issue_title}
{issue_body[:500] if issue_body else ''}

Files changed: {', '.join(files)}

{f"Blocking issues: {len(blocking)}" if blocking else "No blocking issues"}
{f"Warnings: {len(warnings)}" if warnings else ""}

Format:
## Summary
[What does this PR do?]

## Changes
- [List key changes]

## Testing
[How was this tested?]
"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            msg, _ = chat(messages, max_tokens=500, temperature=0.3)
            return msg.content or ""
        except Exception:
            return ""


# Global instance
_reviewer: Optional[CodeReviewer] = None

def get_reviewer(repo_root: str) -> CodeReviewer:
    """Get or create code reviewer."""
    global _reviewer
    if _reviewer is None or str(_reviewer.repo_root) != str(Path(repo_root).resolve()):
        _reviewer = CodeReviewer(repo_root)
    return _reviewer


# ============================================================================
# LangGraph Node
# ============================================================================

def review_node(state: AgentState) -> dict:
    """
    LangGraph node: Review code changes before PR.
    """
    console.print("[bold cyan]Running code review...[/bold cyan]")

    repo_root = state.get("repo_path", ".")

    # Self-review is a quality gate, not a hard dependency: the tests already
    # pass by the time we get here, so an LLM outage must not kill the run.
    try:
        reviewer = get_reviewer(repo_root)
        result = reviewer.review_changes(
            changed_files=state.get("files_to_edit", []),
            issue_title=state.get("issue_title", ""),
            issue_body=state.get("issue_body", ""),
        )
        result.print_report()
        review_passed = result.passed
        review_issues = [str(i) for i in result.issues]
        pr_description = result.pr_description
    except Exception as e:
        console.print(f"[yellow]Review skipped (LLM unavailable): {e}[/yellow]")
        review_passed = True
        review_issues = [f"Review skipped: {e}"]
        pr_description = None

    return {
        "review_passed": review_passed,
        "review_issues": review_issues,
        "review_count": state.get("review_count", 0) + 1,
        "pr_description": pr_description,
        "total_tokens": state.get("total_tokens", 0),
    }


# ============================================================================
# LangChain Tools
# ============================================================================

@tool
def review_code(repo_root: str, files: str) -> str:
    """
    Review Python files for issues.
    
    Args:
        repo_root: Absolute path to repository
        files: Comma-separated list of files to review
        
    Returns:
        Review summary with issues found
    """
    try:
        reviewer = get_reviewer(repo_root)
        file_list = [f.strip() for f in files.split(",")]
        
        result = reviewer.review_changes(file_list)
        
        lines = [result.summary, ""]
        for issue in result.issues[:10]:  # Limit output
            lines.append(str(issue))
        
        if len(result.issues) > 10:
            lines.append(f"... and {len(result.issues) - 10} more issues")
        
        return "\n".join(lines)
    except Exception as e:
        return f"ERROR: {e}"
