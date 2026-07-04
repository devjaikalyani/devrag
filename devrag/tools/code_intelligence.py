"""
code_intelligence.py — AST-based code understanding tools.

Provides semantic code analysis capabilities:
- Function/class signature extraction
- Call graph analysis
- Import dependency tracking
- Code pattern matching
- Style-aware code generation

This enables the agent to:
- Understand code structure without reading entire files
- Find all callers/callees of a function
- Detect circular imports
- Match existing code style
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from langchain_core.tools import tool
from rich.console import Console

console = Console()


@dataclass
class FunctionInfo:
    """Information about a function."""
    name: str
    file_path: str
    line_number: int
    signature: str
    docstring: Optional[str]
    decorators: List[str]
    parameters: List[Dict[str, Any]]
    return_type: Optional[str]
    calls: List[str]  # Functions this function calls
    is_async: bool = False
    is_method: bool = False
    class_name: Optional[str] = None


@dataclass
class ClassInfo:
    """Information about a class."""
    name: str
    file_path: str
    line_number: int
    docstring: Optional[str]
    bases: List[str]
    methods: List[str]
    class_variables: List[str]
    instance_variables: List[str]
    decorators: List[str]


@dataclass
class ImportInfo:
    """Information about imports in a file."""
    file_path: str
    imports: List[str]           # import x
    from_imports: Dict[str, List[str]]  # from x import y, z
    relative_imports: List[str]  # from . import x


class CodeAnalyzer:
    """Analyzes Python code using AST."""
    
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root).resolve()
        self._function_cache: Dict[str, List[FunctionInfo]] = {}
        self._class_cache: Dict[str, List[ClassInfo]] = {}
        self._import_cache: Dict[str, ImportInfo] = {}
        self._call_graph: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_call_graph: Dict[str, Set[str]] = defaultdict(set)
    
    def _safe_path(self, rel_path: str) -> Path:
        """Resolve path safely within repo."""
        target = (self.repo_root / rel_path).resolve()
        if not str(target).startswith(str(self.repo_root)):
            raise PermissionError(f"Path traversal blocked: {rel_path}")
        return target
    
    def _parse_file(self, rel_path: str) -> Optional[ast.Module]:
        """Parse a Python file to AST."""
        try:
            path = self._safe_path(rel_path)
            source = path.read_text(encoding="utf-8")
            return ast.parse(source, filename=str(path))
        except (SyntaxError, FileNotFoundError, PermissionError) as e:
            return None
    
    def get_functions(self, rel_path: str) -> List[FunctionInfo]:
        """Extract all functions from a file."""
        if rel_path in self._function_cache:
            return self._function_cache[rel_path]
        
        tree = self._parse_file(rel_path)
        if not tree:
            return []
        
        functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Get parent class if method
                class_name = None
                for parent in ast.walk(tree):
                    if isinstance(parent, ast.ClassDef):
                        if node in ast.walk(parent):
                            class_name = parent.name
                            break
                
                func_info = self._extract_function_info(node, rel_path, class_name)
                functions.append(func_info)
        
        self._function_cache[rel_path] = functions
        return functions
    
    def _extract_function_info(
        self, 
        node: ast.FunctionDef | ast.AsyncFunctionDef, 
        file_path: str,
        class_name: Optional[str] = None,
    ) -> FunctionInfo:
        """Extract function information from AST node."""
        # Build signature
        params = []
        for arg in node.args.args:
            param = {"name": arg.arg}
            if arg.annotation:
                param["type"] = ast.unparse(arg.annotation)
            params.append(param)
        
        # Get return type
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)
        
        # Build signature string
        param_strs = []
        for p in params:
            s = p["name"]
            if "type" in p:
                s += f": {p['type']}"
            param_strs.append(s)
        
        signature = f"def {node.name}({', '.join(param_strs)})"
        if return_type:
            signature += f" -> {return_type}"
        
        # Get docstring
        docstring = ast.get_docstring(node)
        
        # Get decorators
        decorators = [ast.unparse(d) for d in node.decorator_list]
        
        # Find function calls within this function
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        
        return FunctionInfo(
            name=node.name,
            file_path=file_path,
            line_number=node.lineno,
            signature=signature,
            docstring=docstring,
            decorators=decorators,
            parameters=params,
            return_type=return_type,
            calls=list(set(calls)),
            is_async=isinstance(node, ast.AsyncFunctionDef),
            is_method=class_name is not None,
            class_name=class_name,
        )
    
    def get_classes(self, rel_path: str) -> List[ClassInfo]:
        """Extract all classes from a file."""
        if rel_path in self._class_cache:
            return self._class_cache[rel_path]
        
        tree = self._parse_file(rel_path)
        if not tree:
            return []
        
        classes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_info = self._extract_class_info(node, rel_path)
                classes.append(class_info)
        
        self._class_cache[rel_path] = classes
        return classes
    
    def _extract_class_info(self, node: ast.ClassDef, file_path: str) -> ClassInfo:
        """Extract class information from AST node."""
        # Get base classes
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(ast.unparse(base))
        
        # Get methods
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)
        
        # Get class variables
        class_vars = []
        instance_vars = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                class_vars.append(item.target.id)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_vars.append(target.id)
        
        # Find instance variables in __init__
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                for child in ast.walk(item):
                    if isinstance(child, ast.Assign):
                        for target in child.targets:
                            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                                if target.value.id == "self":
                                    instance_vars.append(target.attr)
        
        # Get decorators
        decorators = [ast.unparse(d) for d in node.decorator_list]
        
        return ClassInfo(
            name=node.name,
            file_path=file_path,
            line_number=node.lineno,
            docstring=ast.get_docstring(node),
            bases=bases,
            methods=methods,
            class_variables=class_vars,
            instance_variables=list(set(instance_vars)),
            decorators=decorators,
        )
    
    def get_imports(self, rel_path: str) -> ImportInfo:
        """Extract imports from a file."""
        if rel_path in self._import_cache:
            return self._import_cache[rel_path]
        
        tree = self._parse_file(rel_path)
        if not tree:
            return ImportInfo(rel_path, [], {}, [])
        
        imports = []
        from_imports = defaultdict(list)
        relative_imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                level = node.level  # Number of dots for relative import
                
                if level > 0:
                    relative_imports.append(f"{'.' * level}{module}")
                
                for alias in node.names:
                    from_imports[module].append(alias.name)
        
        info = ImportInfo(
            file_path=rel_path,
            imports=imports,
            from_imports=dict(from_imports),
            relative_imports=relative_imports,
        )
        self._import_cache[rel_path] = info
        return info
    
    def find_function(self, func_name: str) -> List[FunctionInfo]:
        """Find all definitions of a function by name."""
        results = []
        
        for py_file in self.repo_root.rglob("*.py"):
            if any(skip in str(py_file) for skip in [".venv", "venv", "__pycache__", "node_modules"]):
                continue
            
            rel_path = str(py_file.relative_to(self.repo_root))
            functions = self.get_functions(rel_path)
            
            for func in functions:
                if func.name == func_name:
                    results.append(func)
        
        return results
    
    def find_callers(self, func_name: str) -> List[Tuple[str, str, int]]:
        """Find all functions that call a given function."""
        callers = []
        
        for py_file in self.repo_root.rglob("*.py"):
            if any(skip in str(py_file) for skip in [".venv", "venv", "__pycache__", "node_modules"]):
                continue
            
            rel_path = str(py_file.relative_to(self.repo_root))
            functions = self.get_functions(rel_path)
            
            for func in functions:
                if func_name in func.calls:
                    callers.append((rel_path, func.name, func.line_number))
        
        return callers
    
    def build_call_graph(self) -> Dict[str, Set[str]]:
        """Build complete call graph for the repository."""
        self._call_graph.clear()
        self._reverse_call_graph.clear()
        
        for py_file in self.repo_root.rglob("*.py"):
            if any(skip in str(py_file) for skip in [".venv", "venv", "__pycache__", "node_modules"]):
                continue
            
            rel_path = str(py_file.relative_to(self.repo_root))
            functions = self.get_functions(rel_path)
            
            for func in functions:
                full_name = f"{rel_path}:{func.name}"
                for called in func.calls:
                    self._call_graph[full_name].add(called)
                    self._reverse_call_graph[called].add(full_name)
        
        return dict(self._call_graph)
    
    def detect_circular_imports(self) -> List[List[str]]:
        """Detect circular import dependencies."""
        # Build import graph
        import_graph: Dict[str, Set[str]] = defaultdict(set)
        
        for py_file in self.repo_root.rglob("*.py"):
            if any(skip in str(py_file) for skip in [".venv", "venv", "__pycache__", "node_modules"]):
                continue
            
            rel_path = str(py_file.relative_to(self.repo_root))
            imports = self.get_imports(rel_path)
            
            for module in imports.imports:
                import_graph[rel_path].add(module)
            for module in imports.from_imports.keys():
                import_graph[rel_path].add(module)
        
        # Find cycles using DFS
        cycles = []
        visited = set()
        rec_stack = set()
        path = []
        
        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in import_graph.get(node, set()):
                # Convert module to file path
                neighbor_path = neighbor.replace(".", "/") + ".py"
                
                if neighbor_path not in visited:
                    if dfs(neighbor_path):
                        return True
                elif neighbor_path in rec_stack:
                    cycle_start = path.index(neighbor_path)
                    cycles.append(path[cycle_start:] + [neighbor_path])
                    return True
            
            path.pop()
            rec_stack.remove(node)
            return False
        
        for node in import_graph.keys():
            if node not in visited:
                dfs(node)
        
        return cycles
    
    def get_code_style(self, rel_path: str) -> Dict[str, Any]:
        """Analyze code style in a file."""
        try:
            path = self._safe_path(rel_path)
            content = path.read_text(encoding="utf-8")
        except:
            return {}
        
        lines = content.split("\n")
        
        # Detect indentation
        indent_sizes = []
        for line in lines:
            stripped = line.lstrip()
            if stripped and not stripped.startswith("#"):
                indent = len(line) - len(stripped)
                if indent > 0:
                    indent_sizes.append(indent)
        
        indent_size = 4  # default
        if indent_sizes:
            # Find GCD of common indents
            from math import gcd
            from functools import reduce
            indent_size = reduce(gcd, indent_sizes) if indent_sizes else 4
        
        # Detect quote style
        single_quotes = content.count("'") - content.count('"""') * 3 - content.count("'''") * 3
        double_quotes = content.count('"') - content.count('"""') * 3
        quote_style = "single" if single_quotes > double_quotes else "double"
        
        # Detect docstring style
        docstring_style = "google"  # default
        if "Args:" in content or "Returns:" in content:
            docstring_style = "google"
        elif ":param" in content or ":return:" in content:
            docstring_style = "sphinx"
        elif "Parameters" in content and "----------" in content:
            docstring_style = "numpy"
        
        # Detect line length
        max_line = max(len(line) for line in lines) if lines else 79
        line_length = 79 if max_line <= 79 else (88 if max_line <= 88 else 120)
        
        return {
            "indent_size": indent_size,
            "quote_style": quote_style,
            "docstring_style": docstring_style,
            "line_length": line_length,
            "has_type_hints": "def " in content and "->" in content,
            "uses_dataclasses": "@dataclass" in content,
            "uses_pydantic": "BaseModel" in content,
        }


# Global analyzer instance
_analyzer: Optional[CodeAnalyzer] = None

def get_analyzer(repo_root: str) -> CodeAnalyzer:
    """Get or create code analyzer for repository."""
    global _analyzer
    if _analyzer is None or str(_analyzer.repo_root) != str(Path(repo_root).resolve()):
        _analyzer = CodeAnalyzer(repo_root)
    return _analyzer


# ============================================================================
# LangChain Tools
# ============================================================================

@tool
def get_function_signature(repo_root: str, file_path: str, function_name: str) -> str:
    """
    Get function signature, docstring, and metadata.
    
    Args:
        repo_root: Absolute path to repository
        file_path: Relative path to Python file
        function_name: Name of the function
        
    Returns:
        JSON string with function details or error message
    """
    import json
    
    try:
        analyzer = get_analyzer(repo_root)
        functions = analyzer.get_functions(file_path)
        
        for func in functions:
            if func.name == function_name:
                return json.dumps({
                    "name": func.name,
                    "signature": func.signature,
                    "docstring": func.docstring,
                    "decorators": func.decorators,
                    "parameters": func.parameters,
                    "return_type": func.return_type,
                    "is_async": func.is_async,
                    "is_method": func.is_method,
                    "class_name": func.class_name,
                    "calls": func.calls,
                    "line_number": func.line_number,
                }, indent=2)
        
        return f"ERROR: Function '{function_name}' not found in {file_path}"
    except Exception as e:
        return f"ERROR: {e}"


@tool
def get_class_info(repo_root: str, file_path: str, class_name: str) -> str:
    """
    Get class structure including methods, attributes, and inheritance.
    
    Args:
        repo_root: Absolute path to repository
        file_path: Relative path to Python file
        class_name: Name of the class
        
    Returns:
        JSON string with class details or error message
    """
    import json
    
    try:
        analyzer = get_analyzer(repo_root)
        classes = analyzer.get_classes(file_path)
        
        for cls in classes:
            if cls.name == class_name:
                return json.dumps({
                    "name": cls.name,
                    "bases": cls.bases,
                    "docstring": cls.docstring,
                    "methods": cls.methods,
                    "class_variables": cls.class_variables,
                    "instance_variables": cls.instance_variables,
                    "decorators": cls.decorators,
                    "line_number": cls.line_number,
                }, indent=2)
        
        return f"ERROR: Class '{class_name}' not found in {file_path}"
    except Exception as e:
        return f"ERROR: {e}"


@tool
def find_callers(repo_root: str, function_name: str) -> str:
    """
    Find all functions that call a given function.
    
    Args:
        repo_root: Absolute path to repository
        function_name: Name of the function to find callers for
        
    Returns:
        List of callers with file path, function name, and line number
    """
    try:
        analyzer = get_analyzer(repo_root)
        callers = analyzer.find_callers(function_name)
        
        if not callers:
            return f"No callers found for '{function_name}'"
        
        result = [f"Callers of '{function_name}':"]
        for file_path, caller_name, line_num in callers:
            result.append(f"  {file_path}:{line_num} - {caller_name}()")
        
        return "\n".join(result)
    except Exception as e:
        return f"ERROR: {e}"


@tool
def get_file_structure(repo_root: str, file_path: str) -> str:
    """
    Get structural overview of a Python file (classes, functions, imports).
    
    Args:
        repo_root: Absolute path to repository
        file_path: Relative path to Python file
        
    Returns:
        Formatted structure overview
    """
    try:
        analyzer = get_analyzer(repo_root)
        
        imports = analyzer.get_imports(file_path)
        classes = analyzer.get_classes(file_path)
        functions = analyzer.get_functions(file_path)
        
        lines = [f"=== {file_path} ===\n"]
        
        # Imports
        if imports.imports or imports.from_imports:
            lines.append("IMPORTS:")
            for imp in imports.imports:
                lines.append(f"  import {imp}")
            for module, names in imports.from_imports.items():
                lines.append(f"  from {module} import {', '.join(names)}")
            lines.append("")
        
        # Classes
        for cls in classes:
            lines.append(f"CLASS {cls.name}" + (f"({', '.join(cls.bases)})" if cls.bases else ""))
            if cls.docstring:
                lines.append(f"  \"{cls.docstring[:100]}...\"" if len(cls.docstring or "") > 100 else f"  \"{cls.docstring}\"")
            for method in cls.methods:
                lines.append(f"  - {method}()")
            lines.append("")
        
        # Standalone functions
        standalone = [f for f in functions if not f.is_method]
        if standalone:
            lines.append("FUNCTIONS:")
            for func in standalone:
                async_prefix = "async " if func.is_async else ""
                lines.append(f"  {async_prefix}{func.signature}")
            lines.append("")
        
        return "\n".join(lines)
    except Exception as e:
        return f"ERROR: {e}"


@tool
def analyze_code_style(repo_root: str, file_path: str) -> str:
    """
    Analyze coding style of a file to match when writing new code.
    
    Args:
        repo_root: Absolute path to repository
        file_path: Relative path to Python file
        
    Returns:
        JSON with style information (indent, quotes, docstrings, etc.)
    """
    import json
    
    try:
        analyzer = get_analyzer(repo_root)
        style = analyzer.get_code_style(file_path)
        
        if not style:
            return f"ERROR: Could not analyze style for {file_path}"
        
        return json.dumps(style, indent=2)
    except Exception as e:
        return f"ERROR: {e}"


@tool
def find_similar_functions(repo_root: str, pattern: str) -> str:
    """
    Find functions matching a name pattern across the codebase.
    
    Args:
        repo_root: Absolute path to repository
        pattern: Regex pattern to match function names
        
    Returns:
        List of matching functions with signatures
    """
    try:
        analyzer = get_analyzer(repo_root)
        regex = re.compile(pattern, re.IGNORECASE)
        matches = []
        
        for py_file in Path(repo_root).rglob("*.py"):
            if any(skip in str(py_file) for skip in [".venv", "venv", "__pycache__", "node_modules"]):
                continue
            
            rel_path = str(py_file.relative_to(repo_root))
            functions = analyzer.get_functions(rel_path)
            
            for func in functions:
                if regex.search(func.name):
                    matches.append(f"{rel_path}:{func.line_number} - {func.signature}")
        
        if not matches:
            return f"No functions matching pattern '{pattern}'"
        
        return f"Functions matching '{pattern}':\n" + "\n".join(matches[:20])
    except Exception as e:
        return f"ERROR: {e}"
