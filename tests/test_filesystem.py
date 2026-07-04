"""Tests for filesystem tools (langchain @tool objects — call via .invoke)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from devrag.tools.filesystem import (
    read_file, write_file, str_replace_in_file, list_directory, search_code,
)
from devrag import config


def test_write_and_read(tmp_path):
    write_file.invoke({"repo_root": str(tmp_path), "path": "hello.txt", "content": "hello world"})
    assert read_file.invoke({"repo_root": str(tmp_path), "path": "hello.txt"}) == "hello world"


def test_read_missing(tmp_path):
    result = read_file.invoke({"repo_root": str(tmp_path), "path": "nope/missing.txt"})
    assert "ERROR" in result


def test_str_replace(tmp_path):
    (tmp_path / "code.py").write_text("def foo():\n    return 1\n")
    result = str_replace_in_file.invoke({
        "repo_root": str(tmp_path), "path": "code.py",
        "old_str": "return 1", "new_str": "return 42",
    })
    assert "ERROR" not in result
    assert "return 42" in (tmp_path / "code.py").read_text()


def test_str_replace_not_found(tmp_path):
    (tmp_path / "code.py").write_text("def foo():\n    pass\n")
    result = str_replace_in_file.invoke({
        "repo_root": str(tmp_path), "path": "code.py",
        "old_str": "NOTEXIST", "new_str": "replacement",
    })
    assert "ERROR" in result


def test_str_replace_ambiguous(tmp_path):
    (tmp_path / "code.py").write_text("x = 1\nx = 1\n")
    result = str_replace_in_file.invoke({
        "repo_root": str(tmp_path), "path": "code.py",
        "old_str": "x = 1", "new_str": "x = 2",
    })
    assert "ERROR" in result


def test_write_file_creates_parent_dirs(tmp_path):
    result = write_file.invoke({
        "repo_root": str(tmp_path), "path": "a/b/new.py", "content": "print('hi')",
    })
    assert "ERROR" not in result
    assert (tmp_path / "a/b/new.py").exists()


def test_write_file_refuses_large_overwrite(tmp_path):
    big = "x" * (config.FILE_SIZE_LIMIT_FOR_WRITE + 1)
    (tmp_path / "big.txt").write_text(big)
    result = write_file.invoke({
        "repo_root": str(tmp_path), "path": "big.txt", "content": "tiny",
    })
    assert "ERROR" in result
    assert (tmp_path / "big.txt").read_text() == big


def test_list_directory(tmp_path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "subdir").mkdir()
    result = list_directory.invoke({"repo_root": str(tmp_path), "path": "."})
    assert "a.py" in result
    assert "subdir" in result


def test_search_code(tmp_path):
    (tmp_path / "foo.py").write_text("def target_function():\n    pass\n")
    (tmp_path / "bar.py").write_text("x = 1\n")
    result = search_code.invoke({
        "repo_root": str(tmp_path), "pattern": "target_function", "file_pattern": "*.py",
    })
    assert "foo.py" in result


def test_read_large_file_trimmed(tmp_path):
    (tmp_path / "big.txt").write_text("x" * (config.TOOL_OUTPUT_LIMIT + 5000))
    result = read_file.invoke({"repo_root": str(tmp_path), "path": "big.txt"})
    assert "TRIMMED" in result
    assert len(result) < config.TOOL_OUTPUT_LIMIT + 2000
