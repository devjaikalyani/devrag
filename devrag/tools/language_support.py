"""
language_support.py — Multi-language support for DevRAG.

Provides language-specific configurations for:
- Python, TypeScript/JavaScript, Rust, Go, Java
- File extensions, test frameworks, linters
- Build commands, package managers
- Code patterns and conventions

This enables the agent to:
- Work effectively with any supported language
- Run appropriate tests and linters
- Understand language-specific patterns
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum

from langchain_core.tools import tool
from rich.console import Console

console = Console()


class Language(Enum):
    """Supported programming languages."""
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    CSHARP = "csharp"
    CPP = "cpp"
    RUBY = "ruby"
    PHP = "php"
    UNKNOWN = "unknown"


@dataclass
class LanguageConfig:
    """Configuration for a programming language."""
    name: str
    language: Language
    extensions: List[str]
    
    # Package management
    package_files: List[str]
    install_command: str
    
    # Testing
    test_frameworks: List[str]
    test_patterns: List[str]  # Glob patterns for test files
    test_commands: Dict[str, str]  # framework -> command
    
    # Linting/Formatting
    linters: List[str]
    lint_commands: Dict[str, str]  # linter -> command
    formatters: List[str]
    format_commands: Dict[str, str]
    
    # Build
    build_files: List[str]
    build_command: Optional[str]
    
    # Code patterns
    function_pattern: str  # Regex for function definitions
    class_pattern: str  # Regex for class definitions
    import_pattern: str  # Regex for imports
    
    # Conventions
    naming_conventions: Dict[str, str]  # function, class, constant, etc.
    comment_style: str  # "//" or "#"
    
    # Additional metadata
    has_types: bool = True
    compiled: bool = False


# ============================================================================
# Language Configurations
# ============================================================================

PYTHON_CONFIG = LanguageConfig(
    name="Python",
    language=Language.PYTHON,
    extensions=[".py", ".pyx", ".pyi"],
    
    package_files=["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"],
    install_command="pip install -r requirements.txt",
    
    test_frameworks=["pytest", "unittest", "nose"],
    test_patterns=["test_*.py", "*_test.py", "tests/*.py"],
    test_commands={
        "pytest": "pytest",
        "unittest": "python -m unittest discover",
    },
    
    linters=["flake8", "pylint", "ruff", "mypy"],
    lint_commands={
        "flake8": "flake8 .",
        "pylint": "pylint **/*.py",
        "ruff": "ruff check .",
        "mypy": "mypy .",
    },
    formatters=["black", "isort", "autopep8"],
    format_commands={
        "black": "black .",
        "isort": "isort .",
    },
    
    build_files=["pyproject.toml", "setup.py"],
    build_command="pip install -e .",
    
    function_pattern=r"^\s*(async\s+)?def\s+(\w+)\s*\(",
    class_pattern=r"^\s*class\s+(\w+)\s*[\(:]",
    import_pattern=r"^\s*(from\s+[\w.]+\s+import|import)\s+",
    
    naming_conventions={
        "function": "snake_case",
        "class": "PascalCase",
        "constant": "UPPER_SNAKE_CASE",
        "variable": "snake_case",
        "module": "snake_case",
    },
    comment_style="#",
    has_types=True,
    compiled=False,
)

TYPESCRIPT_CONFIG = LanguageConfig(
    name="TypeScript",
    language=Language.TYPESCRIPT,
    extensions=[".ts", ".tsx"],
    
    package_files=["package.json", "yarn.lock", "pnpm-lock.yaml"],
    install_command="npm install",
    
    test_frameworks=["jest", "vitest", "mocha", "playwright"],
    test_patterns=["*.test.ts", "*.spec.ts", "__tests__/*.ts"],
    test_commands={
        "jest": "npm test",
        "vitest": "npx vitest",
        "mocha": "npx mocha",
    },
    
    linters=["eslint", "tslint"],
    lint_commands={
        "eslint": "npx eslint .",
    },
    formatters=["prettier"],
    format_commands={
        "prettier": "npx prettier --write .",
    },
    
    build_files=["tsconfig.json", "package.json"],
    build_command="npm run build",
    
    function_pattern=r"^\s*(export\s+)?(async\s+)?function\s+(\w+)|^\s*(\w+)\s*[:=]\s*(async\s+)?\(",
    class_pattern=r"^\s*(export\s+)?class\s+(\w+)",
    import_pattern=r"^\s*import\s+",
    
    naming_conventions={
        "function": "camelCase",
        "class": "PascalCase",
        "constant": "UPPER_SNAKE_CASE",
        "variable": "camelCase",
        "interface": "PascalCase",
    },
    comment_style="//",
    has_types=True,
    compiled=True,
)

JAVASCRIPT_CONFIG = LanguageConfig(
    name="JavaScript",
    language=Language.JAVASCRIPT,
    extensions=[".js", ".jsx", ".mjs", ".cjs"],
    
    package_files=["package.json"],
    install_command="npm install",
    
    test_frameworks=["jest", "mocha", "vitest"],
    test_patterns=["*.test.js", "*.spec.js", "__tests__/*.js"],
    test_commands={
        "jest": "npm test",
        "mocha": "npx mocha",
    },
    
    linters=["eslint"],
    lint_commands={
        "eslint": "npx eslint .",
    },
    formatters=["prettier"],
    format_commands={
        "prettier": "npx prettier --write .",
    },
    
    build_files=["package.json", "webpack.config.js", "vite.config.js"],
    build_command="npm run build",
    
    function_pattern=r"^\s*(export\s+)?(async\s+)?function\s+(\w+)|^\s*(const|let|var)\s+(\w+)\s*=\s*(async\s+)?\(",
    class_pattern=r"^\s*(export\s+)?class\s+(\w+)",
    import_pattern=r"^\s*(import|require)\s*\(",
    
    naming_conventions={
        "function": "camelCase",
        "class": "PascalCase",
        "constant": "UPPER_SNAKE_CASE",
        "variable": "camelCase",
    },
    comment_style="//",
    has_types=False,
    compiled=False,
)

RUST_CONFIG = LanguageConfig(
    name="Rust",
    language=Language.RUST,
    extensions=[".rs"],
    
    package_files=["Cargo.toml", "Cargo.lock"],
    install_command="cargo build",
    
    test_frameworks=["cargo"],
    test_patterns=["**/tests/*.rs", "src/**/*_test.rs"],
    test_commands={
        "cargo": "cargo test",
    },
    
    linters=["clippy"],
    lint_commands={
        "clippy": "cargo clippy",
    },
    formatters=["rustfmt"],
    format_commands={
        "rustfmt": "cargo fmt",
    },
    
    build_files=["Cargo.toml"],
    build_command="cargo build --release",
    
    function_pattern=r"^\s*(pub\s+)?(async\s+)?fn\s+(\w+)",
    class_pattern=r"^\s*(pub\s+)?struct\s+(\w+)|^\s*(pub\s+)?enum\s+(\w+)",
    import_pattern=r"^\s*use\s+",
    
    naming_conventions={
        "function": "snake_case",
        "struct": "PascalCase",
        "constant": "UPPER_SNAKE_CASE",
        "variable": "snake_case",
        "module": "snake_case",
    },
    comment_style="//",
    has_types=True,
    compiled=True,
)

GO_CONFIG = LanguageConfig(
    name="Go",
    language=Language.GO,
    extensions=[".go"],
    
    package_files=["go.mod", "go.sum"],
    install_command="go mod download",
    
    test_frameworks=["go test"],
    test_patterns=["*_test.go"],
    test_commands={
        "go test": "go test ./...",
    },
    
    linters=["golint", "golangci-lint"],
    lint_commands={
        "golangci-lint": "golangci-lint run",
    },
    formatters=["gofmt"],
    format_commands={
        "gofmt": "go fmt ./...",
    },
    
    build_files=["go.mod"],
    build_command="go build ./...",
    
    function_pattern=r"^\s*func\s+(\([^)]+\)\s+)?(\w+)\s*\(",
    class_pattern=r"^\s*type\s+(\w+)\s+struct",
    import_pattern=r"^\s*import\s+",
    
    naming_conventions={
        "function": "PascalCase/camelCase",  # Exported/unexported
        "struct": "PascalCase",
        "constant": "PascalCase",
        "variable": "camelCase",
        "package": "lowercase",
    },
    comment_style="//",
    has_types=True,
    compiled=True,
)

JAVA_CONFIG = LanguageConfig(
    name="Java",
    language=Language.JAVA,
    extensions=[".java"],
    
    package_files=["pom.xml", "build.gradle", "build.gradle.kts"],
    install_command="mvn install -DskipTests",
    
    test_frameworks=["junit", "testng"],
    test_patterns=["*Test.java", "*Tests.java", "Test*.java"],
    test_commands={
        "maven": "mvn test",
        "gradle": "./gradlew test",
    },
    
    linters=["checkstyle", "spotbugs"],
    lint_commands={
        "checkstyle": "mvn checkstyle:check",
    },
    formatters=["google-java-format"],
    format_commands={},
    
    build_files=["pom.xml", "build.gradle"],
    build_command="mvn package -DskipTests",
    
    function_pattern=r"^\s*(public|private|protected)?\s*(static\s+)?\w+\s+(\w+)\s*\(",
    class_pattern=r"^\s*(public|private)?\s*(abstract\s+)?(class|interface|enum)\s+(\w+)",
    import_pattern=r"^\s*import\s+",
    
    naming_conventions={
        "function": "camelCase",
        "class": "PascalCase",
        "constant": "UPPER_SNAKE_CASE",
        "variable": "camelCase",
        "package": "lowercase",
    },
    comment_style="//",
    has_types=True,
    compiled=True,
)


# ============================================================================
# Language Registry
# ============================================================================

LANGUAGE_CONFIGS: Dict[Language, LanguageConfig] = {
    Language.PYTHON: PYTHON_CONFIG,
    Language.TYPESCRIPT: TYPESCRIPT_CONFIG,
    Language.JAVASCRIPT: JAVASCRIPT_CONFIG,
    Language.RUST: RUST_CONFIG,
    Language.GO: GO_CONFIG,
    Language.JAVA: JAVA_CONFIG,
}

EXTENSION_TO_LANGUAGE: Dict[str, Language] = {}
for config in LANGUAGE_CONFIGS.values():
    for ext in config.extensions:
        EXTENSION_TO_LANGUAGE[ext] = config.language


# ============================================================================
# Language Detection
# ============================================================================

class LanguageDetector:
    """Detect and configure languages for a repository."""
    
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root).resolve()
        self._detected_languages: Optional[Set[Language]] = None
        self._primary_language: Optional[Language] = None
    
    def detect_languages(self) -> Set[Language]:
        """Detect all languages used in the repository."""
        if self._detected_languages is not None:
            return self._detected_languages
        
        languages = set()
        file_counts: Dict[Language, int] = {}
        
        for path in self.repo_root.rglob("*"):
            if path.is_file():
                # Skip common non-source directories
                if any(skip in str(path) for skip in [
                    ".git", "node_modules", ".venv", "venv", 
                    "__pycache__", "target", "build", "dist"
                ]):
                    continue
                
                ext = path.suffix.lower()
                if ext in EXTENSION_TO_LANGUAGE:
                    lang = EXTENSION_TO_LANGUAGE[ext]
                    languages.add(lang)
                    file_counts[lang] = file_counts.get(lang, 0) + 1
        
        # Also check for package files
        for config in LANGUAGE_CONFIGS.values():
            for pkg_file in config.package_files:
                if (self.repo_root / pkg_file).exists():
                    languages.add(config.language)
        
        self._detected_languages = languages
        
        # Determine primary language
        if file_counts:
            self._primary_language = max(file_counts, key=file_counts.get)
        
        return languages
    
    def get_primary_language(self) -> Optional[Language]:
        """Get the primary language of the repository."""
        if self._primary_language is None:
            self.detect_languages()
        return self._primary_language
    
    def get_config(self, language: Language) -> Optional[LanguageConfig]:
        """Get configuration for a language."""
        return LANGUAGE_CONFIGS.get(language)
    
    def detect_test_framework(self, language: Language) -> Optional[str]:
        """Detect which test framework is used for a language."""
        config = LANGUAGE_CONFIGS.get(language)
        if not config:
            return None
        
        # Check for framework-specific files
        framework_indicators = {
            # Python
            "pytest": ["pytest.ini", "pyproject.toml", "conftest.py"],
            "unittest": [],  # Default for Python
            
            # JavaScript/TypeScript
            "jest": ["jest.config.js", "jest.config.ts"],
            "vitest": ["vitest.config.js", "vitest.config.ts"],
            "mocha": [".mocharc.js", ".mocharc.json"],
            
            # Rust
            "cargo": ["Cargo.toml"],
            
            # Go
            "go test": ["go.mod"],
        }
        
        for framework in config.test_frameworks:
            if framework in framework_indicators:
                for indicator in framework_indicators[framework]:
                    if (self.repo_root / indicator).exists():
                        return framework
        
        # Return first available framework as default
        return config.test_frameworks[0] if config.test_frameworks else None
    
    def detect_linter(self, language: Language) -> Optional[str]:
        """Detect which linter is configured for a language."""
        config = LANGUAGE_CONFIGS.get(language)
        if not config:
            return None
        
        linter_indicators = {
            # Python
            "ruff": ["ruff.toml", "pyproject.toml"],
            "flake8": [".flake8", "setup.cfg"],
            "pylint": [".pylintrc"],
            
            # JavaScript/TypeScript
            "eslint": [".eslintrc", ".eslintrc.js", ".eslintrc.json"],
            
            # Rust
            "clippy": ["Cargo.toml"],
        }
        
        for linter in config.linters:
            if linter in linter_indicators:
                for indicator in linter_indicators[linter]:
                    if (self.repo_root / indicator).exists():
                        # Additional check for pyproject.toml
                        if indicator == "pyproject.toml":
                            content = (self.repo_root / indicator).read_text()
                            if linter in content.lower():
                                return linter
                        else:
                            return linter
        
        return config.linters[0] if config.linters else None
    
    def get_test_command(self, language: Language = None) -> Optional[str]:
        """Get the test command for the repository."""
        if language is None:
            language = self.get_primary_language()
        
        if not language:
            return None
        
        framework = self.detect_test_framework(language)
        config = LANGUAGE_CONFIGS.get(language)
        
        if config and framework:
            return config.test_commands.get(framework)
        
        return None
    
    def get_lint_command(self, language: Language = None) -> Optional[str]:
        """Get the lint command for the repository."""
        if language is None:
            language = self.get_primary_language()
        
        if not language:
            return None
        
        linter = self.detect_linter(language)
        config = LANGUAGE_CONFIGS.get(language)
        
        if config and linter:
            return config.lint_commands.get(linter)
        
        return None
    
    def get_build_command(self, language: Language = None) -> Optional[str]:
        """Get the build command for the repository."""
        if language is None:
            language = self.get_primary_language()
        
        if not language:
            return None
        
        config = LANGUAGE_CONFIGS.get(language)
        return config.build_command if config else None


# Global instance
_detector: Optional[LanguageDetector] = None

def get_detector(repo_root: str) -> LanguageDetector:
    """Get or create language detector."""
    global _detector
    if _detector is None or str(_detector.repo_root) != str(Path(repo_root).resolve()):
        _detector = LanguageDetector(repo_root)
    return _detector


# ============================================================================
# LangChain Tools
# ============================================================================

@tool
def detect_repository_languages(repo_root: str) -> str:
    """
    Detect programming languages used in a repository.
    
    Args:
        repo_root: Absolute path to repository
        
    Returns:
        JSON with detected languages and primary language
    """
    import json
    
    try:
        detector = get_detector(repo_root)
        languages = detector.detect_languages()
        primary = detector.get_primary_language()
        
        result = {
            "languages": [lang.value for lang in languages],
            "primary": primary.value if primary else None,
        }
        
        # Add detected frameworks
        if primary:
            result["test_framework"] = detector.detect_test_framework(primary)
            result["linter"] = detector.detect_linter(primary)
            result["test_command"] = detector.get_test_command(primary)
            result["lint_command"] = detector.get_lint_command(primary)
            result["build_command"] = detector.get_build_command(primary)
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"ERROR: {e}"


@tool
def get_language_config(language_name: str) -> str:
    """
    Get configuration for a programming language.
    
    Args:
        language_name: Name of the language (python, typescript, rust, go, java)
        
    Returns:
        JSON with language configuration
    """
    import json
    
    try:
        language = Language(language_name.lower())
        config = LANGUAGE_CONFIGS.get(language)
        
        if not config:
            return f"Unknown language: {language_name}"
        
        result = {
            "name": config.name,
            "extensions": config.extensions,
            "package_files": config.package_files,
            "install_command": config.install_command,
            "test_frameworks": config.test_frameworks,
            "test_patterns": config.test_patterns,
            "linters": config.linters,
            "formatters": config.formatters,
            "naming_conventions": config.naming_conventions,
            "has_types": config.has_types,
            "compiled": config.compiled,
        }
        
        return json.dumps(result, indent=2)
    except ValueError:
        return f"Unknown language: {language_name}. Supported: python, typescript, javascript, rust, go, java"
    except Exception as e:
        return f"ERROR: {e}"
