"""lado.fingerprint on real git repositories: what a turn of a read-only agent changed."""

import subprocess

import pytest

from lado import fingerprint


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def take(cwd, repo=None):
    """The fingerprint of `cwd`, in the session repository `repo` (default: `cwd`)."""
    return fingerprint.take(str(cwd), str(repo or cwd), fingerprint.BUDGET)


@pytest.fixture
def base(repo):
    """The repo with a tracked file, an ignore rule and a commit."""
    (repo / "a.txt").write_text("a\n")
    (repo / ".gitignore").write_text("*.log\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "a")
    return repo


def test_nothing_changed_is_no_difference(base):
    assert fingerprint.diff(take(base), take(base)) == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda r: (r / "a.txt").write_text("b\n"), ["changed: a.txt"]),
        (lambda r: (r / "new.py").write_text("x\n"), ["new: new.py"]),
        (lambda r: (r / "a.txt").unlink(), ["deleted: a.txt"]),
        (
            lambda r: (r / "d" / "e").mkdir(parents=True) or (r / "d/e/f.txt").write_text(""),
            ["new: d/e/f.txt"],
        ),
        (lambda r: git(r, "tag", "v1"), ["tag v1 added"]),
        (lambda r: git(r, "checkout", "-qb", "other"), ["on branch main -> other"]),
    ],
)
def test_a_change_of_the_repository_is_named(base, change, expected):
    before = take(base)
    change(base)
    assert fingerprint.diff(before, take(base)) == expected


def test_a_commit_moves_head_and_the_branch(base):
    before = take(base)
    old = before["head"]
    (base / "a.txt").write_text("b\n")
    git(base, "commit", "-qam", "b")
    after = take(base)
    assert fingerprint.diff(before, after) == [
        f"HEAD {old[:7]} -> {after['head'][:7]}",
        "branch main moved",
    ]


def test_a_file_changed_again_is_a_change_and_one_put_back_too(base):
    (base / "a.txt").write_text("b\n")
    before = take(base)
    (base / "a.txt").write_text("c\n")
    assert fingerprint.diff(before, take(base)) == ["changed: a.txt"]
    middle = take(base)
    (base / "a.txt").write_text("a\n")
    assert fingerprint.diff(middle, take(base)) == ["changed: a.txt"]


def test_a_stash_is_a_change(base):
    (base / "a.txt").write_text("b\n")
    before = take(base)
    git(base, "stash", "-q")
    assert fingerprint.diff(before, take(base)) == ["stash changed", "changed: a.txt"]


def test_ignored_files_lado_and_a_file_gone_again_are_none(base):
    before = take(base)
    (base / "run.log").write_text("x\n")
    (base / ".lado" / "kits").mkdir(parents=True)
    (base / ".lado" / "kits" / "k.yaml").write_text("x\n")
    (base / "tmp.txt").write_text("x\n")
    (base / "tmp.txt").unlink()
    assert fingerprint.diff(before, take(base)) == []


def test_in_a_worktree_the_main_branch_and_its_tags_count_but_other_branches_do_not(base):
    tree = base / ".lado" / "worktrees" / "s" / "w1"
    git(base, "worktree", "add", "-qb", "lado/s/w1", str(tree), "HEAD")
    git(base, "worktree", "add", "-qb", "lado/s/w2", str(base.parent / "w2"), "HEAD")
    before = take(tree, base)
    assert before["branch"] == "lado/s/w1"
    (base.parent / "w2" / "x.txt").write_text("x\n")
    git(base.parent / "w2", "add", ".")
    git(base.parent / "w2", "commit", "-qm", "x")  # another agent's branch
    assert fingerprint.diff(before, take(tree, base)) == []
    git(base, "commit", "-q", "--allow-empty", "-m", "on main")
    assert fingerprint.diff(before, take(tree, base)) == ["branch main moved"]
    git(base, "checkout", "-qb", "next")
    assert fingerprint.diff(before, take(tree, base)) == ["main branch main -> next"]


def test_without_a_main_branch_its_ref_is_left_out(base):
    git(base, "checkout", "-q", "--detach")
    before = take(base)
    assert (before["branch"], before["main"]) == (None, None)
    git(base, "commit", "-q", "--allow-empty", "-m", "detached")
    after = take(base)
    assert fingerprint.diff(before, after) == [f"HEAD {before['head'][:7]} -> {after['head'][:7]}"]


def test_a_fingerprint_is_small_and_holds_no_file_contents(base):
    (base / "a.txt").write_text("SECRET-CONTENT\n")
    taken = take(base)
    assert "SECRET-CONTENT" not in repr(taken)
    assert set(taken) == {"head", "branch", "main", "refs", "files"}


def test_git_failing_or_too_slow_is_a_fingerprint_error(tmp_path, base, monkeypatch):
    with pytest.raises(fingerprint.FingerprintError, match="not a git repository"):
        fingerprint.take(str(tmp_path), str(tmp_path), fingerprint.BUDGET)
    with pytest.raises(fingerprint.FingerprintError, match="longer than 0.0001 s"):
        fingerprint.take(str(base), str(base), 0.0001)
