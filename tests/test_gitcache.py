import subprocess
from urllib.parse import quote

import pytest
from agent_helpers import init_repo, publish

from lado import gitcache

SKILL = "---\nname: {0}\ndescription: use {0}\n---\nDo {0}.\n"


@pytest.fixture
def work(tmp_path):
    """The repository behind a pack, published to a bare repo as the remote."""
    return init_repo(tmp_path / "pack")


def head(path) -> str:
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.mark.parametrize(
    ("spec", "location", "ref"),
    [
        ("https://example.com/o/kits.git", "https://example.com/o/kits.git", None),
        ("https://example.com/o/kits@v1.0.0", "https://example.com/o/kits", "v1.0.0"),
        ("git@example.com:o/kits.git", "git@example.com:o/kits.git", None),
        ("git@example.com:o/kits.git@feature/x", "git@example.com:o/kits.git", "feature/x"),
        ("ssh://git@example.com/o/kits", "ssh://git@example.com/o/kits", None),
        ("./kits@dev", "./kits", "dev"),
        ("../my-pack", "../my-pack", None),
    ],
)
def test_split_ref(spec, location, ref):
    assert gitcache.split_ref(spec) == (location, ref)


@pytest.mark.parametrize(
    ("location", "git"),
    [
        ("https://github.com/o/r", True),
        ("git@github.com:o/r", True),
        ("/srv/repos/pack.git", True),
        ("../my-pack", False),
        ("pack", False),
    ],
)
def test_is_git(location, git):
    assert gitcache.is_git(location) is git


def test_fetch_pinned_clones_once_per_address_and_ref(work, lado_home):
    url = publish(work, {"skills/a/SKILL.md": SKILL.format("a")}, tag="v1.0.0")
    v1 = head(work)
    publish(work, {"skills/b/SKILL.md": SKILL.format("b")}, tag="v1.1.0")

    clone = gitcache.fetch_pinned(url, "v1.0.0")
    repo_dir = clone.parent
    assert clone.parent.parent == lado_home / "cache"
    assert repo_dir.name.startswith("pack-") and len(repo_dir.name) == len("pack-") + 8
    assert clone.name == "v1.0.0"
    assert head(clone) == v1 and not (clone / "skills" / "b").exists()
    assert gitcache.versions(clone) == ["1.0.0"]
    assert gitcache.address(clone) == url
    assert gitcache.ref(clone) == "v1.0.0"
    # Only the clone is left: no temporary folder beside it.
    assert sorted(p.name for p in repo_dir.iterdir()) == ["v1.0.0"]

    by_commit = gitcache.fetch_pinned(url, head(work))
    assert by_commit.parent == repo_dir and (by_commit / "skills" / "b").is_dir()
    assert gitcache.clone_root(by_commit / "skills" / "b") == by_commit
    assert gitcache.clone_root(work) is None
    # A ref with a slash is one folder.
    subprocess.run(["git", "-C", str(work), "tag", "rel/2"], check=True)
    subprocess.run(["git", "-C", str(work), "push", "-q", url, "rel/2"], check=True)
    assert gitcache.fetch_pinned(url, "rel/2").name == quote("rel/2", safe="")


def test_a_ready_clone_does_not_run_git(work, monkeypatch):
    url = publish(work, {"skills/a/SKILL.md": SKILL.format("a")}, tag="v1.0.0")
    clone = gitcache.fetch_pinned(url, "v1.0.0")

    def no_git(*args, **kwargs):
        raise AssertionError(f"git ran: {args}")

    monkeypatch.setattr(gitcache.subprocess, "run", no_git)
    assert gitcache.fetch_pinned(url, "v1.0.0") == clone


@pytest.mark.parametrize(
    ("ref", "error"),
    [
        ("main", "main is a branch of {url}; pin a tag or a commit"),
        ("nope", 'cannot get {url}@nope: no tag or commit "nope"'),
    ],
)
def test_fetch_errors_leave_nothing(work, lado_home, ref, error):
    url = publish(work, {"skills/a/SKILL.md": SKILL.format("a")}, tag="v1.0.0")
    with pytest.raises(gitcache.GitError, match=error.format(url=url)):
        gitcache.fetch_pinned(url, ref)
    assert [p for p in (lado_home / "cache").rglob("*") if p.is_dir()] == [
        gitcache.clone_dir(url, ref).parent
    ]


def test_git_error_names_the_address_and_ref(lado_home):
    with pytest.raises(gitcache.GitError, match="cannot get file:///nowhere/x.git@v1: .*"):
        gitcache.fetch_pinned("file:///nowhere/x.git", "v1")
