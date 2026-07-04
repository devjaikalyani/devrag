"""
refactor.py — Handle large-scale refactoring operations.

Specialized agent for:
- Renaming functions/classes/variables across codebase
- Moving code between files
- Extracting modules from large files
- Updating import statements
- Maintaining consistency during refactoring

This enables the agent to handle issues like:
- "Rename User to Account everywhere"
- "Extract authentication into separate module"
- "Move all database models to models/ directory"
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

from langchain_core.tools import tool
from rich.console import Console

from .state import AgentState
from devrag.llm.client import chat
from devrag.tools.code_intelligence import get_analyzer, CodeAnalyzer

console = Console()


@dataclass
class RefactorChange:
    """A single change in a refactoring operation."""
    file_path: str
    line_number: int
    old_text: str
    new_text: str
    change_type: str  # "rename", "move", "import", "delete"


@dataclass
class RefactorPlan:
    """Plan for a refactoring operation."""
    operation: str
    description: str
    affected_files: List[str]
    changes: List[RefactorChange]
    warnings: List[str] = field(default_factory=list)
    
    def summary(self) -> str:
        """Get human-readable summary."""
        lines = [
            f"Refactoring: {self.operation}",
            f"Description: {self.description}",
            f"Affected files: {len(self.affected_files)}",
            f"Total changes: {len(self.changes)}",
        ]
        if self.warnings:
            lines.append(f"Warnings: {len(self.warnings)}")
            for w in self.warnings[:3]:
                lines.append(f"  - {w}")
        return "\n".join(lines)


class RefactorEngine:
    """Engine for performing refactoring operations."""
    
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root).resolve()
        self.analyzer = get_analyzer(str(self.repo_root))
    
    def _safe_path(self, rel_path: str) -> Path:
        """Resolve path safely within repo."""
        target = (self.repo_root / rel_path).resolve()
        if not str(target).startswith(str(self.repo_root)):
            raise PermissionError(f"Path traversal blocked: {rel_path}")
        return target
    
    def _get_python_files(self) -> List[str]:
        """Get all Python files in repository."""
        files = []
        for py_file in self.repo_root.rglob("*.py"):
            if any(skip in str(py_file) for skip in [".venv", "venv", "__pycache__", "node_modules", ".git"]):
                continue
            files.append(str(py_file.relative_to(self.repo_root)))
        return files
    
    def rename_symbol(
        self,
        old_name: str,
        new_name: str,
        symbol_type: str = "auto",  # "function", "class", "variable", "auto"
        scope: str = None,  # Limit to specific file or directory
    ) -> RefactorPlan:
        """
        Rename a symbol across the codebase.
        
        Args:
            old_name: Current name
            new_name: New name
            symbol_type: Type of symbol (auto-detected if "auto")
            scope: Limit scope to specific path
        """
        console.print(f"[bold cyan]Renaming {old_name} -> {new_name}[/bold cyan]")
        
        changes = []
        affected_files = set()
        warnings = []
        
        # Get files to process
        files = self._get_python_files()
        if scope:
            files = [f for f in files if f.startswith(scope)]
        
        # Build pattern based on symbol type
        if symbol_type == "class":
            # Match class definitions and type hints
            patterns = [
                (rf'\bclass\s+{old_name}\b', f'class {new_name}'),
                (rf'\b{old_name}\b(?=\s*\()', new_name),  # Instantiation
                (rf':\s*{old_name}\b', f': {new_name}'),  # Type hints
                (rf'->\s*{old_name}\b', f'-> {new_name}'),  # Return types
                (rf'\[{old_name}\]', f'[{new_name}]'),  # Generic types
            ]
        elif symbol_type == "function":
            patterns = [
                (rf'\bdef\s+{old_name}\b', f'def {new_name}'),
                (rf'\b{old_name}\s*\(', f'{new_name}('),  # Calls
            ]
        else:
            # Auto: match word boundaries
            patterns = [(rf'\b{old_name}\b', new_name)]
        
        for file_path in files:
            try:
                full_path = self._safe_path(file_path)
                content = full_path.read_text(encoding="utf-8")
                lines = content.split("\n")
                
                for i, line in enumerate(lines, start=1):
                    for pattern, replacement in patterns:
                        if re.search(pattern, line):
                            new_line = re.sub(pattern, replacement, line)
                            if new_line != line:
                                changes.append(RefactorChange(
                                    file_path=file_path,
                                    line_number=i,
                                    old_text=line,
                                    new_text=new_line,
                                    change_type="rename",
                                ))
                                affected_files.add(file_path)
            except Exception as e:
                warnings.append(f"Failed to process {file_path}: {e}")
        
        return RefactorPlan(
            operation=f"Rename {old_name} -> {new_name}",
            description=f"Rename {symbol_type} '{old_name}' to '{new_name}'",
            affected_files=list(affected_files),
            changes=changes,
            warnings=warnings,
        )
    
    def move_function(
        self,
        func_name: str,
        source_file: str,
        target_file: str,
    ) -> RefactorPlan:
        """
        Move a function from one file to another.
        
        Handles:
        - Moving the function definition
        - Updating imports in both files
        - Updating call sites
        """
        console.print(f"[bold cyan]Moving {func_name} to {target_file}[/bold cyan]")
        
        changes = []
        affected_files = set()
        warnings = []
        
        # Parse source file
        source_path = self._safe_path(source_file)
        source_content = source_path.read_text(encoding="utf-8")
        
        try:
            tree = ast.parse(source_content)
        except SyntaxError as e:
            return RefactorPlan(
                operation=f"Move {func_name}",
                description=f"FAILED: {e}",
                affected_files=[],
                changes=[],
                warnings=[f"Syntax error in {source_file}: {e}"],
            )
        
        # Find the function
        func_node = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == func_name:
                    func_node = node
                    break
        
        if not func_node:
            return RefactorPlan(
                operation=f"Move {func_name}",
                description=f"Function {func_name} not found in {source_file}",
                affected_files=[],
                changes=[],
                warnings=[f"Function {func_name} not found"],
            )
        
        # Extract function source
        lines = source_content.split("\n")
        func_lines = lines[func_node.lineno - 1:func_node.end_lineno]
        func_source = "\n".join(func_lines)
        
        # Detect imports the function needs
        needed_imports = self._detect_function_imports(func_node, tree)
        
        # 1. Add function to target file
        target_path = self._safe_path(target_file)
        if target_path.exists():
            target_content = target_path.read_text(encoding="utf-8")
        else:
            target_content = '"""Module."""\n'
        
        # Add imports and function
        new_target = target_content.rstrip() + "\n\n" + func_source + "\n"
        changes.append(RefactorChange(
            file_path=target_file,
            line_number=len(target_content.split("\n")) + 1,
            old_text="",
            new_text=func_source,
            change_type="move",
        ))
        affected_files.add(target_file)
        
        # 2. Remove function from source (and add re-export)
        new_source_lines = lines[:func_node.lineno - 1] + lines[func_node.end_lineno:]
        
        # Add import from new location
        target_module = target_file.replace("/", ".").replace("\\", ".").rstrip(".py")
        re_export = f"from {target_module} import {func_name}"
        new_source_lines.insert(0, re_export)
        
        changes.append(RefactorChange(
            file_path=source_file,
            line_number=func_node.lineno,
            old_text=func_source,
            new_text=f"# Moved to {target_file}\n{re_export}",
            change_type="move",
        ))
        affected_files.add(source_file)
        
        # 3. Update import statements in other files
        source_module = source_file.replace("/", ".").replace("\\", ".").rstrip(".py")
        
        for file_path in self._get_python_files():
            if file_path in (source_file, target_file):
                continue
            
            try:
                content = self._safe_path(file_path).read_text(encoding="utf-8")
                
                # Check if file imports the function
                import_pattern = rf"from\s+{re.escape(source_module)}\s+import\s+.*?\b{func_name}\b"
                if re.search(import_pattern, content):
                    # Update to import from new location
                    new_content = re.sub(
                        import_pattern,
                        f"from {target_module} import {func_name}",
                        content,
                    )
                    
                    if new_content != content:
                        changes.append(RefactorChange(
                            file_path=file_path,
                            line_number=1,  # Import usually at top
                            old_text=f"import from {source_module}",
                            new_text=f"import from {target_module}",
                            change_type="import",
                        ))
                        affected_files.add(file_path)
            except Exception as e:
                warnings.append(f"Failed to update imports in {file_path}: {e}")
        
        return RefactorPlan(
            operation=f"Move {func_name}",
            description=f"Move {func_name} from {source_file} to {target_file}",
            affected_files=list(affected_files),
            changes=changes,
            warnings=warnings,
        )
    
    def _detect_function_imports(self, func_node: ast.AST, module: ast.Module) -> Set[str]:
        """Detect what imports a function needs."""
        # Get all names used in the function
        used_names = set()
        for node in ast.walk(func_node):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)
        
        # Get module-level imports
        imports = {}
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imports[name] = ast.unparse(node)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imports[name] = ast.unparse(node)
        
        # Find which imports are needed
        needed = set()
        for name in used_names:
            if name in imports:
                needed.add(imports[name])
        
        return needed
    
    def extract_module(
        self,
        source_file: str,
        target_file: str,
        items: List[str],  # Functions/classes to extract
    ) -> RefactorPlan:
        """
        Extract functions/classes into a new module.
        
        Args:
            source_file: File to extract from
            target_file: New file to create
            items: Names of functions/classes to extract
        """
        console.print(f"[bold cyan]Extracting to {target_file}[/bold cyan]")
        
        changes = []
        affected_files = set()
        warnings = []
        
        # Parse source
        source_path = self._safe_path(source_file)
        source_content = source_path.read_text(encoding="utf-8")
        
        try:
            tree = ast.parse(source_content)
        except SyntaxError as e:
            return RefactorPlan(
                operation="Extract module",
                description=f"FAILED: {e}",
                affected_files=[],
                changes=[],
                warnings=[str(e)],
            )
        
        lines = source_content.split("\n")
        
        # Find items to extract
        extracted_code = []
        removed_ranges = []  # (start_line, end_line) to remove
        
        for node in ast.iter_child_nodes(tree):
            name = None
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
            elif isinstance(node, ast.ClassDef):
                name = node.name
            
            if name and name in items:
                item_lines = lines[node.lineno - 1:node.end_lineno]
                extracted_code.append("\n".join(item_lines))
                removed_ranges.append((node.lineno - 1, node.end_lineno))
        
        if not extracted_code:
            return RefactorPlan(
                operation="Extract module",
                description=f"No items found: {items}",
                affected_files=[],
                changes=[],
                warnings=[f"Items not found: {items}"],
            )
        
        # Build new module
        header = f'"""{target_file} - Extracted from {source_file}."""\n'
        
        # Copy relevant imports
        imports_to_copy = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports_to_copy.append(ast.unparse(node))
        
        new_module = header + "\n".join(imports_to_copy) + "\n\n" + "\n\n".join(extracted_code)
        
        changes.append(RefactorChange(
            file_path=target_file,
            line_number=1,
            old_text="",
            new_text=new_module,
            change_type="move",
        ))
        affected_files.add(target_file)
        
        # Update source file
        # Remove extracted items (in reverse order to preserve line numbers)
        new_lines = lines.copy()
        for start, end in sorted(removed_ranges, reverse=True):
            del new_lines[start:end]
        
        # Add re-export
        target_module = target_file.replace("/", ".").replace("\\", ".").rstrip(".py")
        re_export = f"from {target_module} import {', '.join(items)}"
        
        # Insert after existing imports
        insert_pos = 0
        for i, line in enumerate(new_lines):
            if line.startswith("import ") or line.startswith("from "):
                insert_pos = i + 1
        new_lines.insert(insert_pos, re_export)
        
        changes.append(RefactorChange(
            file_path=source_file,
            line_number=1,
            old_text=f"Contains {items}",
            new_text=f"Re-exports from {target_file}",
            change_type="move",
        ))
        affected_files.add(source_file)
        
        return RefactorPlan(
            operation="Extract module",
            description=f"Extract {items} to {target_file}",
            affected_files=list(affected_files),
            changes=changes,
            warnings=warnings,
        )
    
    def apply_plan(self, plan: RefactorPlan, dry_run: bool = False) -> Dict[str, str]:
        """
        Apply a refactoring plan.
        
        Args:
            plan: The refactoring plan to apply
            dry_run: If True, only preview changes
            
        Returns:
            Dict mapping file paths to their new contents
        """
        results = {}
        
        # Group changes by file
        changes_by_file: Dict[str, List[RefactorChange]] = defaultdict(list)
        for change in plan.changes:
            changes_by_file[change.file_path].append(change)
        
        for file_path, changes in changes_by_file.items():
            try:
                full_path = self._safe_path(file_path)
                
                if full_path.exists():
                    content = full_path.read_text(encoding="utf-8")
                else:
                    content = ""
                
                lines = content.split("\n") if content else []
                
                # Apply changes (handle both renames and moves)
                for change in changes:
                    if change.change_type == "rename":
                        # Replace specific line
                        if 0 < change.line_number <= len(lines):
                            lines[change.line_number - 1] = change.new_text
                    elif change.change_type == "move":
                        # Append new content
                        lines.append(change.new_text)
                
                new_content = "\n".join(lines)
                results[file_path] = new_content
                
                if not dry_run:
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(new_content, encoding="utf-8")
                    console.print(f"[green]Updated:[/green] {file_path}")
                else:
                    console.print(f"[dim]Would update:[/dim] {file_path}")
            
            except Exception as e:
                console.print(f"[red]Failed to update {file_path}: {e}[/red]")
        
        return results


# Global instance
_engine: Optional[RefactorEngine] = None

def get_engine(repo_root: str) -> RefactorEngine:
    """Get or create refactor engine."""
    global _engine
    if _engine is None or str(_engine.repo_root) != str(Path(repo_root).resolve()):
        _engine = RefactorEngine(repo_root)
    return _engine


# ============================================================================
# LangChain Tools
# ============================================================================

@tool
def plan_rename(
    repo_root: str,
    old_name: str,
    new_name: str,
    symbol_type: str = "auto",
    scope: str = None,
) -> str:
    """
    Plan renaming a symbol across the codebase.
    
    Args:
        repo_root: Absolute path to repository
        old_name: Current name of the symbol
        new_name: New name for the symbol
        symbol_type: Type of symbol (function, class, variable, or auto)
        scope: Optional path to limit scope
        
    Returns:
        Summary of the refactoring plan
    """
    try:
        engine = get_engine(repo_root)
        plan = engine.rename_symbol(old_name, new_name, symbol_type, scope)
        return plan.summary()
    except Exception as e:
        return f"ERROR: {e}"


@tool
def execute_rename(
    repo_root: str,
    old_name: str,
    new_name: str,
    symbol_type: str = "auto",
    scope: str = None,
) -> str:
    """
    Execute renaming a symbol across the codebase.
    
    Args:
        repo_root: Absolute path to repository
        old_name: Current name of the symbol
        new_name: New name for the symbol
        symbol_type: Type of symbol (function, class, variable, or auto)
        scope: Optional path to limit scope
        
    Returns:
        Result of the refactoring operation
    """
    try:
        engine = get_engine(repo_root)
        plan = engine.rename_symbol(old_name, new_name, symbol_type, scope)
        
        if not plan.changes:
            return f"No changes needed - '{old_name}' not found"
        
        results = engine.apply_plan(plan)
        return f"Renamed {old_name} -> {new_name} in {len(results)} files"
    except Exception as e:
        return f"ERROR: {e}"


@tool
def plan_move_function(
    repo_root: str,
    func_name: str,
    source_file: str,
    target_file: str,
) -> str:
    """
    Plan moving a function to a different file.
    
    Args:
        repo_root: Absolute path to repository
        func_name: Name of the function to move
        source_file: Current file path (relative)
        target_file: Destination file path (relative)
        
    Returns:
        Summary of the refactoring plan
    """
    try:
        engine = get_engine(repo_root)
        plan = engine.move_function(func_name, source_file, target_file)
        return plan.summary()
    except Exception as e:
        return f"ERROR: {e}"


@tool
def plan_extract_module(
    repo_root: str,
    source_file: str,
    target_file: str,
    items: str,  # Comma-separated list
) -> str:
    """
    Plan extracting functions/classes into a new module.
    
    Args:
        repo_root: Absolute path to repository
        source_file: File to extract from
        target_file: New file to create
        items: Comma-separated names of items to extract
        
    Returns:
        Summary of the refactoring plan
    """
    try:
        engine = get_engine(repo_root)
        items_list = [i.strip() for i in items.split(",")]
        plan = engine.extract_module(source_file, target_file, items_list)
        return plan.summary()
    except Exception as e:
        return f"ERROR: {e}"
