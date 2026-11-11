"""scripts/test_audit.py pseudo: functions emptied one at a time in a copy of the repository,
never in its working tree, also when it is interrupted (openspec capability test-audit)."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

SCRIPT = Path(__file__).parents[2] / "scripts" / "test_audit.py"

CORE = """\
def checked(x):
    return x + 1


def executed(x):
    return x * 2


def ready():
    return True
"""

TESTS = """\
from lado.core import checked, executed, ready


def test_checked():
    assert checked(1) == 2


def test_executed():
    executed(3)


def test_ready():
    while not ready():
        pass
"""

# The lines of each function's body in CORE, as `coverage` records them.
COVERAGE = {
    "tests/test_core.py::test_checked": {"src/lado/core.py": [2]},
    "tests/test_core.py::test_executed": {"src/lado/core.py": [6]},
    "tests/test_core.py::test_ready": {"src/lado/core.py": [10]},
}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def tiny_repo(tmp_path: Path, package: str = "src/lado") -> Path:
    """A repository with a package `lado` (module `core`) and its tests, committed."""
    repo = tmp_path / "repo"
    (repo / package).mkdir(parents=True)
    (repo / package / "__init__.py").write_text("")
    (repo / package / "core.py").write_text(CORE)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_core.py").write_text(TESTS)
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "tiny")
    return repo


def pseudo_command(tmp_path: Path, repo: Path, *extra: str) -> list[str]:
    coverage = tmp_path / "coverage-unit.json"
    coverage.write_text(json.dumps(COVERAGE))
    out = tmp_path / "out"
    audit = [sys.executable, str(SCRIPT), "--out", str(out), "pseudo", "--repo", str(repo)]
    return [*audit, "--modules", "core", "--coverage", str(coverage), *extra]


def clean(repo: Path) -> None:
    assert git(repo, "status", "--porcelain") == ""
    assert len(git(repo, "worktree", "list").splitlines()) == 1  # the copy is gone


def test_pseudo_finds_a_function_no_test_checks(tmp_path):
    repo = tiny_repo(tmp_path)
    result = subprocess.run(
        pseudo_command(tmp_path, repo, "--timeout", "5"),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    found = json.loads((tmp_path / "out" / "pseudo.json").read_text())
    assert found["pseudo"] == {"core.executed": ["tests/test_core.py::test_executed"]}
    assert found["killed"] == ["core.checked"]
    assert found["timeout"] == ["core.ready"]  # its test loops for ever: ended, counted killed
    assert found["not_covered"] == []
    clean(repo)


def test_pseudo_leaves_the_working_tree_clean(tmp_path):
    repo = tiny_repo(tmp_path)
    subprocess.run(pseudo_command(tmp_path, repo, "--timeout", "5"), check=True, timeout=120)
    assert (repo / "src" / "lado" / "core.py").read_text() == CORE
    clean(repo)


def test_an_interrupted_pseudo_leaves_it_clean(tmp_path):
    repo = tiny_repo(tmp_path)
    audit = subprocess.Popen(
        pseudo_command(tmp_path, repo, "--timeout", "60"),
        stdout=subprocess.PIPE,
        text=True,
        start_new_session=True,  # its own group, as a terminal's job gets Ctrl-C
    )
    try:
        for line in audit.stdout:
            if "core.ready" in line:  # its test now loops on the emptied function
                break
        time.sleep(1)
        os.killpg(audit.pid, signal.SIGINT)
        assert audit.wait(timeout=30) == 130
    finally:
        if audit.poll() is None:
            os.killpg(audit.pid, signal.SIGKILL)
    clean(repo)
    assert not (tmp_path / "out" / "pseudo-copy").exists()


def test_a_copy_whose_lado_is_another_s_is_refused(tmp_path):
    repo = tiny_repo(tmp_path, package="lado")  # no src/: the copy would import LADO's lado
    result = subprocess.run(
        pseudo_command(tmp_path, repo), capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 2
    assert "imports lado from" in result.stdout
    assert not (tmp_path / "out" / "pseudo.json").exists()
    clean(repo)
