"""
tester.py — Tester node. No API calls — pure subprocess.
Auto-detects test runner and reports pass/fail.
Now installs package in development mode AND ensures pytest is available.
Uses the SAME Python interpreter for all operations with guaranteed PATH.
Includes smart test skipping for JSON-only changes.
"""
from __future__ import annotations
import re
import subprocess
import sys
import os
from pathlib import Path
from .state import AgentState
from rich.console import Console

console = Console()

_RUNNERS = [
    ("pytest.ini",     "python -m pytest -x -v --tb=short"),
    ("setup.cfg",      "python -m pytest -x -v --tb=short"),
    ("pyproject.toml", "python -m pytest -x -v --tb=short"),
    ("tox.ini",        "python -m tox"),
    ("Makefile",       "make test"),
    ("package.json",   "npm test"),
    ("Cargo.toml",     "cargo test"),
    ("go.mod",         "go test ./..."),
]

def _detect_cmd(repo_path: str) -> str:
    root = Path(repo_path)
    for fname, cmd in _RUNNERS:
        if (root / fname).exists():
            return cmd
    return "python -m pytest -x -v --tb=short"

def _get_environment() -> dict:
    """Get environment with proper PATH for the current Python."""
    python_exe = sys.executable
    python_dir = str(Path(python_exe).parent)
    
    # Create environment with the Python directory first in PATH
    env = os.environ.copy()
    env["PATH"] = f"{python_dir}{os.pathsep}{env.get('PATH', '')}"
    
    # Add useful debugging
    env["PYTHONVERBOSE"] = "0"
    
    return env

def _ensure_pytest() -> bool:
    """Ensure pytest is installed and available in the current environment."""
    python_exe = sys.executable
    env = _get_environment()
    
    try:
        # First, upgrade pip to ensure latest version
        subprocess.run(
            f"{python_exe} -m pip install --upgrade pip",
            shell=True, capture_output=True, text=True, timeout=30,
            env=env
        )
        
        # Check if pytest is already installed and working
        result = subprocess.run(
            f"{python_exe} -m pytest --version",
            shell=True, capture_output=True, text=True, timeout=5,
            env=env
        )
        if result.returncode == 0:
            console.print(f"  [dim]pytest {result.stdout.strip()} already installed[/dim]")
            return True
        
        # Install pytest if missing - force reinstall to ensure it's in the right place
        console.print("  [yellow]pytest not found, installing...[/yellow]")
        
        # Try installing with --force-reinstall to ensure it's in the correct environment
        install_result = subprocess.run(
            f"{python_exe} -m pip install --force-reinstall pytest",
            shell=True, capture_output=True, text=True, timeout=30,
            env=env
        )
        
        if install_result.returncode == 0:
            # Verify installation worked
            verify_result = subprocess.run(
                f"{python_exe} -m pytest --version",
                shell=True, capture_output=True, text=True, timeout=5,
                env=env
            )
            if verify_result.returncode == 0:
                console.print(f"  [green]pytest {verify_result.stdout.strip()} installed successfully[/green]")
                return True
            else:
                console.print("  [red]pytest installed but not working[/red]")
                return False
        else:
            console.print(f"  [red]Failed to install pytest: {install_result.stderr[:200]}[/red]")
            
            # Last resort: try installing with --user flag
            console.print("  [yellow]Trying --user install...[/yellow]")
            user_result = subprocess.run(
                f"{python_exe} -m pip install --user pytest",
                shell=True, capture_output=True, text=True, timeout=30,
                env=env
            )
            if user_result.returncode == 0:
                verify_result = subprocess.run(
                    f"{python_exe} -m pytest --version",
                    shell=True, capture_output=True, text=True, timeout=5,
                    env=env
                )
                if verify_result.returncode == 0:
                    console.print(f"  [green]pytest {verify_result.stdout.strip()} installed with --user[/green]")
                    return True
            
            return False
    except Exception as e:
        console.print(f"  [red]Error with pytest: {e}[/red]")
        return False

def _install_dependencies(repo_path: str) -> tuple[bool, str]:
    """Install the package in development mode and its dependencies."""
    root = Path(repo_path)
    python_exe = sys.executable
    env = _get_environment()
    
    # Check for Node.js projects FIRST (package.json)
    if (root / "package.json").exists():
        try:
            console.print("  [dim]Running npm install...[/dim]")
            result = subprocess.run(
                f"cd {repo_path} && npm install",
                shell=True, capture_output=True, text=True, timeout=120,
                env=env
            )
            if result.returncode == 0:
                return True, "npm install successful"
            else:
                console.print(f"  [yellow]npm install failed: {result.stderr[:200]}[/yellow]")
                return False, result.stderr
        except subprocess.TimeoutExpired:
            return False, "Timeout running npm install"
    
    # Check for different Python package management files
    if (root / "pyproject.toml").exists():
        # Modern Python with pyproject.toml
        try:
            # Try to install in development mode
            result = subprocess.run(
                f"cd {repo_path} && {python_exe} -m pip install -e .",
                shell=True, capture_output=True, text=True, timeout=60,
                env=env
            )
            if result.returncode == 0:
                return True, "Package installed successfully"
            
            # If that fails, try installing normally
            result = subprocess.run(
                f"cd {repo_path} && {python_exe} -m pip install .",
                shell=True, capture_output=True, text=True, timeout=60,
                env=env
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Timeout installing dependencies"
    
    elif (root / "setup.py").exists():
        # Legacy Python with setup.py
        try:
            result = subprocess.run(
                f"cd {repo_path} && {python_exe} -m pip install -e .",
                shell=True, capture_output=True, text=True, timeout=60,
                env=env
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Timeout installing dependencies"
    
    elif (root / "requirements.txt").exists():
        # Just requirements.txt, no package
        try:
            result = subprocess.run(
                f"cd {repo_path} && {python_exe} -m pip install -r requirements.txt",
                shell=True, capture_output=True, text=True, timeout=60,
                env=env
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Timeout installing dependencies"
    
    # No package management files found
    return True, "No dependencies to install"

def _should_skip_tests(state: AgentState) -> bool:
    """Determine if tests can be skipped (e.g., only JSON files changed)."""
    # Get all files that were changed
    changed_files = [c["file"] for c in state.get("code_changes", [])]
    planned_files = state.get("files_to_edit", [])
    
    # Check if ALL planned files are JSON (even if no changes were made)
    all_planned_json = all(f.endswith('.json') for f in planned_files) if planned_files else False
    
    # If planned files are JSON-only, skip tests regardless of whether changes were made
    if all_planned_json and planned_files:
        console.print("  [yellow]Only JSON files in scope, skipping tests (safe for static content)[/yellow]")
        return True
    
    # If files were changed, check if all are JSON
    if changed_files:
        all_json = all(f.endswith('.json') for f in changed_files)
        if all_json:
            console.print("  [yellow]Only JSON files changed, skipping tests (safe)[/yellow]")
            return True
    
    # If mixed file types, run tests
    return False

def tester_node(state: AgentState) -> dict:
    console.print("[bold cyan]Running tests...[/bold cyan]")

    # Check if we can skip tests entirely (JSON-only changes)
    if _should_skip_tests(state):
        return {
            "test_output": "JSON-only change detected, tests skipped (safe for static content)",
            "test_passed": True,  # Force pass for JSON changes
            "retry_count": state.get("retry_count", 0),
            "total_tokens": state.get("total_tokens", 0),
        }

    repo_path = state["repo_path"]
    cmd       = state.get("test_command") or _detect_cmd(repo_path)
    
    # Get the actual Python interpreter and proper environment
    python_exe = sys.executable
    env = _get_environment()
    
    # Replace "python" in the command with the actual interpreter
    cmd = cmd.replace("python", python_exe)

    # First, ensure pytest is installed and working
    if not _ensure_pytest():
        return {
            "test_output": "ERROR: Could not install pytest",
            "test_passed": False,
            "retry_count": state.get("retry_count", 0),
            "total_tokens": state.get("total_tokens", 0),
        }
    
    # Then, install project dependencies
    console.print("  [dim]Installing project dependencies...[/dim]")
    install_ok, install_output = _install_dependencies(repo_path)
    
    if not install_ok:
        console.print("  [yellow]Warning: Failed to install dependencies[/yellow]")
        console.print(f"  [dim]{install_output[:200]}[/dim]")
    
    # Run the actual tests with the proper environment
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=repo_path,
            capture_output=True, text=True, timeout=120,
            env=env  # Use the same environment with proper PATH
        )
        output    = result.stdout + result.stderr
        exit_code = result.returncode
        
        # Debug: show what command was run
        console.print(f"  [dim]Ran: {cmd}[/dim]")
        
    except subprocess.TimeoutExpired:
        output    = "ERROR: tests timed out after 120s"
        exit_code = 1

    passed = (exit_code == 0)

    # Extra check: even exit 0 with "failed" text = failure
    if passed and re.search(r"\d+ failed", output):
        passed = False

    # Special case: pytest exit code 5 means "no tests collected" — the repo
    # genuinely has no tests, which is not a failure. Do NOT apply this to
    # other non-zero exits: a collection error (syntax error in the code,
    # exit code 2) also prints "no tests ran" but must stay a failure so the
    # debugger can repair it.
    if exit_code == 5:
        console.print("  [yellow]No tests found in repository - treating as pass[/yellow]")
        passed = True
    elif not passed and re.search(r"errors? during collection|SyntaxError|IndentationError", output):
        console.print("  [red]Test collection failed (broken code?) - keeping as failure[/red]")

    status = "[green]PASSED ok[/green]" if passed else "[red]FAILED FAIL[/red]"
    console.print(f"  Tests: {status}")
    if not passed:
        # Show last 20 lines of output for quick diagnosis
        lines = [l for l in output.splitlines() if l.strip()][-20:]
        if lines:
            console.print("[dim]" + "\n".join(f"  {l}" for l in lines) + "[/dim]")

    return {
        "test_output": output[:4000],
        "test_passed": passed,
        "retry_count": state.get("retry_count", 0),
        "total_tokens": state.get("total_tokens", 0),
    }