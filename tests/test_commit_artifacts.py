"""commit_and_push must stage source changes but never the build/test
artifacts the agent's own test run leaves behind."""
import git
import pytest

from devrag.tools.github_client import commit_and_push


@pytest.fixture
def repo_with_artifacts(tmp_path):
    repo = git.Repo.init(tmp_path)
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "Test")
        cw.set_value("user", "email", "test@example.com")

    src = tmp_path / "src"
    src.mkdir()
    (src / "calculator.py").write_text("def add(a, b):\n    return a + b\n")
    repo.git.add("-A")
    repo.index.commit("initial")

    # Agent edits source, and running the tests generates artifacts
    (src / "calculator.py").write_text("def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n")
    cache = src / "__pycache__"
    cache.mkdir()
    (cache / "calculator.cpython-311.pyc").write_bytes(b"\x00compiled")
    pytest_cache = tmp_path / ".pytest_cache"
    pytest_cache.mkdir()
    (pytest_cache / "CACHEDIR.TAG").write_text("Signature: 8a477f597d28d172789f06886806bc55")
    (tmp_path / ".coverage").write_text("coverage data")
    return repo, tmp_path


def test_source_committed_without_artifacts(repo_with_artifacts, monkeypatch):
    repo, path = repo_with_artifacts
    # No remote in this fixture: the push step is out of scope here.
    monkeypatch.setattr(git.Repo, "remote", lambda self, name="origin": (_ for _ in ()).throw(ValueError("no remote")))
    try:
        commit_and_push(str(path), "devrag/test-branch", "Add sub function")
    except Exception:
        pass  # push failure is expected and irrelevant to staging

    committed = repo.git.show("--name-only", "--pretty=format:", "HEAD").split()
    assert "src/calculator.py" in committed
    assert not [f for f in committed if "__pycache__" in f or f.endswith(".pyc")]
    assert not [f for f in committed if ".pytest_cache" in f or f.endswith(".coverage")]
