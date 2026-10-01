import subprocess

import pytest
import yaml
from agent_helpers import init_repo, publish

from lado import sources

SKILL = "---\nname: {0}\ndescription: use {0}\n---\nDo {0}.\n"


@pytest.fixture
def work(tmp_path):
    """The repository behind a git source, published to a bare repo as the remote."""
    return init_repo(tmp_path / "pack")


def head(path) -> str:
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_registry_keeps_order_and_refuses_duplicates(tmp_path, lado_home):
    assert sources.registered() == []
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    sources.add(str(tmp_path / "b"))
    sources.add(str(tmp_path / "a"), "first-a")
    assert [s.name for s in sources.registered()] == ["b", "first-a"]
    saved = yaml.safe_load((lado_home / "sources.yaml").read_text())
    assert saved == {
        "sources": [
            {"name": "b", "kind": "path", "location": str((tmp_path / "b").resolve())},
            {"name": "first-a", "kind": "path", "location": str((tmp_path / "a").resolve())},
        ]
    }
    with pytest.raises(sources.SourceError, match='a source named "b" already exists'):
        sources.add(str(tmp_path / "a"), "b")
    with pytest.raises(sources.SourceError, match='no source "nope"; sources: b, first-a'):
        sources.get("nope")
    (lado_home / "sources.yaml").write_text("sources:\n- {name: x, kind: svn, location: y}\n")
    with pytest.raises(sources.SourceError, match="invalid source"):
        sources.registered()


def test_path_source_is_read_in_place(tmp_path):
    folder = tmp_path / "My Kits"
    folder.mkdir()
    source = sources.add(str(folder))
    assert (source.name, source.kind, source.path()) == ("my-kits", "path", folder.resolve())
    assert source.update().startswith("nothing to update; read in place")
    assert (source.revision(), source.versions()) == (None, [])
    removed, files = sources.remove("my-kits")
    assert removed == source and files == f"kept the folder {folder.resolve()}"
    assert folder.is_dir() and sources.registered() == []
    with pytest.raises(sources.SourceError, match="is not a folder"):
        sources.add(str(tmp_path / "missing"))
    with pytest.raises(sources.SourceError, match="a local folder has no ref"):
        sources.add(f"{folder}@v1")


@pytest.mark.parametrize(
    ("spec", "location", "ref"),
    [
        ("https://example.com/o/kits.git", "https://example.com/o/kits.git", None),
        ("https://example.com/o/kits@v1.0.0", "https://example.com/o/kits", "v1.0.0"),
        ("git@example.com:o/kits.git", "git@example.com:o/kits.git", None),
        ("git@example.com:o/kits.git@feature/x", "git@example.com:o/kits.git", "feature/x"),
        ("ssh://git@example.com/o/kits", "ssh://git@example.com/o/kits", None),
        ("./kits@dev", "./kits", "dev"),
    ],
)
def test_split_ref(spec, location, ref):
    assert sources._split_ref(spec) == (location, ref)


def test_git_source_clones_checks_out_and_updates(work, lado_home):
    url = publish(work, {"skills/a/SKILL.md": SKILL.format("a")}, tag="v1.0.0")
    v1 = head(work)
    publish(work, {"skills/b/SKILL.md": SKILL.format("b")})

    latest = sources.add(url)
    assert (latest.name, latest.kind, latest.ref) == ("pack", "git", None)
    assert latest.path() == lado_home / "sources" / "pack"
    assert (latest.path() / "skills" / "b").is_dir()
    assert latest.versions() == []

    pinned = sources.add(f"{url}@v1.0.0", "pinned")
    assert pinned.ref == "v1.0.0" and pinned.revision() == v1
    assert not (pinned.path() / "skills" / "b").exists()
    assert pinned.versions() == ["1.0.0"]
    assert pinned.describe() == f"git {url} @v1.0.0"

    publish(work, {"skills/c/SKILL.md": SKILL.format("c")}, tag="v1.1.0-rc.1")
    assert latest.update() == f"at {head(work)}"
    assert (latest.path() / "skills" / "c").is_dir() and latest.versions() == ["1.1.0-rc.1"]
    assert pinned.update() == f"at {v1}"

    # A moved tag is followed.
    subprocess.run(["git", "-C", str(work), "tag", "-f", "v1.0.0"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(work), "push", "-q", "-f", url, "v1.0.0"], check=True, capture_output=True
    )
    assert pinned.update() == f"at {head(work)}"

    _, files = sources.remove("pinned")
    assert files == f"deleted the clone {lado_home / 'sources' / 'pinned'}"
    assert not pinned.path().exists() and [s.name for s in sources.registered()] == ["pack"]


def test_git_source_follows_a_branch(work):
    url = publish(work, {"skills/a/SKILL.md": SKILL.format("a")})
    git = ["git", "-C", str(work)]
    subprocess.run([*git, "checkout", "-q", "-b", "dev"], check=True)
    publish(work, {"skills/d/SKILL.md": SKILL.format("d")})
    subprocess.run([*git, "push", "-q", url, "dev"], check=True)
    source = sources.add(f"{url}@dev")
    assert source.revision() == head(work)
    publish(work, {"skills/e/SKILL.md": SKILL.format("e")})
    subprocess.run([*git, "push", "-q", url, "dev"], check=True)
    assert source.update() == f"at {head(work)}"
    assert (source.path() / "skills" / "e").is_dir()


def test_git_source_reclones_a_missing_clone(work):
    source = sources.add(publish(work, {"skills/a/SKILL.md": SKILL.format("a")}))
    subprocess.run(["rm", "-rf", str(source.path())], check=True)
    assert source.update() == f"at {head(work)}"


def test_git_errors_are_clear_and_leave_nothing(work, lado_home):
    url = publish(work, {"skills/a/SKILL.md": SKILL.format("a")})
    with pytest.raises(
        sources.SourceError, match=f'cannot get git {url} @nope: no tag, branch or commit "nope"'
    ):
        sources.add(f"{url}@nope")
    with pytest.raises(sources.SourceError, match="cannot get git file:///nowhere/x.git"):
        sources.add("file:///nowhere/x.git")
    assert sources.registered() == [] and not (lado_home / "sources" / "pack").exists()
