"""scripts/release_check.py: a final release is the code of its last release candidate
(the Release workflow, docs/release.md)."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "release_check.py"

PYPROJECT = '[project]\nname = "x"\nversion = "{version}"\ndependencies = []\n'
LOCK = (
    'version = 1\n\n[[package]]\nname = "x"\nversion = "{version}"\nsource = {{ editable = "." }}\n'
)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


class Repo:
    """A repository of a package `x` whose releases the test commits and tags."""

    def __init__(self, path: Path):
        self.path = path
        path.mkdir()
        git(path, "init", "-q", "-b", "main")
        git(path, "config", "user.email", "test@example.com")
        git(path, "config", "user.name", "test")
        git(path, "config", "commit.gpgsign", "false")
        git(path, "config", "tag.gpgsign", "false")
        self.write("src/x.py", "def x():\n    return 1\n")
        self.write("CHANGELOG.md", "# Changelog\n\n## 0.37.0 (unreleased)\n")

    def write(self, name: str, text: str) -> None:
        file = self.path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)

    def release(self, version: str) -> None:
        """Set the version in pyproject.toml and uv.lock, commit and tag it."""
        self.write("pyproject.toml", PYPROJECT.format(version=version))
        self.write("uv.lock", LOCK.format(version=version))
        git(self.path, "add", "-A")
        git(self.path, "commit", "-q", "-m", f"Release {version}")
        git(self.path, "tag", f"v{version}")

    def check(self, tag: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), tag],
            cwd=self.path,
            capture_output=True,
            text=True,
            timeout=30,
        )


@pytest.fixture
def repo(tmp_path) -> Repo:
    return Repo(tmp_path / "repo")


def passes(done: subprocess.CompletedProcess) -> bool:
    assert done.returncode in (0, 1), done.stderr
    return done.returncode == 0 and done.stderr == ""


def test_a_release_candidate_passes(repo):
    repo.release("0.37.0rc1")
    assert passes(repo.check("v0.37.0rc1"))


def test_a_final_with_only_its_version_and_the_changelog_changed_passes(repo):
    repo.release("0.37.0rc1")
    repo.write("CHANGELOG.md", "# Changelog\n\n## 0.37.0 (2026-10-20)\n")
    repo.release("0.37.0")
    done = repo.check("v0.37.0")
    assert passes(done)
    assert "v0.37.0 is the code of v0.37.0rc1" in done.stdout


def test_a_final_with_code_its_release_candidate_did_not_have_fails(repo):
    repo.release("0.37.0rc1")
    repo.write("src/x.py", "def x():\n    return 2\n")
    repo.write("src/new.py", "")
    repo.release("0.37.0")
    done = repo.check("v0.37.0")
    assert done.returncode == 1
    assert done.stderr.splitlines() == [
        "v0.37.0 differs from v0.37.0rc1 in src/new.py",
        "v0.37.0 differs from v0.37.0rc1 in src/x.py",
    ]


def test_a_final_that_changes_another_line_of_pyproject_fails(repo):
    repo.release("0.37.0rc1")
    repo.write("pyproject.toml", PYPROJECT.format(version="0.37.0").replace("[]", '["y"]'))
    repo.write("uv.lock", LOCK.format(version="0.37.0"))
    git(repo.path, "commit", "-q", "-am", "Release 0.37.0")
    git(repo.path, "tag", "v0.37.0")
    done = repo.check("v0.37.0")
    assert done.returncode == 1
    assert done.stderr.splitlines() == [
        "v0.37.0 changes a line of pyproject.toml that is not its version: -dependencies = []",
        'v0.37.0 changes a line of pyproject.toml that is not its version: +dependencies = ["y"]',
    ]


def test_a_minor_release_without_a_release_candidate_fails(repo):
    repo.release("0.38.0")
    done = repo.check("v0.38.0")
    assert done.returncode == 1
    assert done.stderr == "v0.38.0 needs a release candidate: tag v0.38.0rc1 first\n"


def test_a_patch_needs_no_release_candidate_but_one_it_has_holds(repo):
    repo.release("0.37.1")
    assert passes(repo.check("v0.37.1"))
    repo.release("0.37.2rc1")
    repo.write("src/x.py", "def x():\n    return 3\n")
    repo.release("0.37.2")
    done = repo.check("v0.37.2")
    assert done.returncode == 1
    assert done.stderr == "v0.37.2 differs from v0.37.2rc1 in src/x.py\n"


def test_the_last_release_candidate_is_the_highest_number(repo):
    repo.release("0.37.0rc2")
    repo.write("src/x.py", "def x():\n    return 10\n")
    repo.release("0.37.0rc10")
    repo.release("0.37.0")
    done = repo.check("v0.37.0")
    assert passes(done)
    assert "v0.37.0rc10" in done.stdout


@pytest.mark.parametrize("tag", ["v1", "nightly", "v0.37.0.post1"])
def test_a_tag_that_is_no_final_release_passes(repo, tag):
    repo.release("0.37.0rc1")
    git(repo.path, "tag", tag)
    assert passes(repo.check(tag))


def test_the_script_imports_only_the_standard_library():
    code = (
        "import sys; sys.path.insert(0, 'scripts'); before = set(sys.modules); "
        "import release_check; "
        "print('\\n'.join(sorted(m for m in set(sys.modules) - before)))"
    )
    loaded = subprocess.run(
        [sys.executable, "-I", "-c", code], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    stdlib = sys.stdlib_module_names
    assert [m for m in loaded if m.split(".")[0] not in stdlib and m != "release_check"] == []
