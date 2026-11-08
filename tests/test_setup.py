"""lado.setup: a plain folder of files made a repository for a session (openspec change
new-session-window, capability folder-setup)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from lado import setup

BIG = setup.MAX_FILE + 1


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("LADO_REPOS", str(ws))
    return ws


@pytest.fixture
def notes(workspace, git_config):
    """A folder of notes with a secret, a key in a subfolder, a large file and a folder of
    another repository."""
    folder = workspace / "notes"
    (folder / "deploy").mkdir(parents=True)
    (folder / "a.txt").write_text("hello\n")
    (folder / ".env").write_text("KEY=1\n")
    (folder / "deploy" / "server.key").write_text("k\n")
    with open(folder / "big.bin", "wb") as big:
        big.truncate(BIG)  # sparse: no space taken on disk
    (folder / "old").mkdir()
    git(folder / "old", "init", "--quiet")
    (folder / "old" / "x").write_text("x\n")
    return folder


def git(path, *args):
    return subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def test_the_preview_counts_what_the_first_commit_takes(notes):
    found = setup.preview(str(notes))
    assert (found.files, found.bytes, found.refusal) == (1, 6, None)
    assert found.left_out == [
        setup.LeftOut(".env", "secret", 6),
        setup.LeftOut("big.bin", "large", BIG),
        setup.LeftOut("deploy/server.key", "secret", 2),
        setup.LeftOut("old/", "repository", None),
    ]
    assert not (notes / ".git").exists()


def test_the_folders_gitignore_is_respected(workspace, git_config):
    folder = workspace / "site"
    (folder / "build").mkdir(parents=True)
    (folder / "build" / "x").write_text("x")
    (folder / "index.html").write_text("<p>")
    (folder / ".gitignore").write_text("build/\n")
    found = setup.preview(str(folder))
    assert (found.files, found.left_out) == (2, [])  # index.html and .gitignore


@pytest.mark.parametrize(
    "name",
    [".env.local", "keys.pem", "a.key", "c.p12", "c.pfx", "id_rsa.pub", "id_ed25519",
     "credentials.json", ".npmrc", ".netrc"],
)  # fmt: skip
def test_a_secret_is_told_by_its_name(workspace, git_config, name):
    folder = workspace / "x"
    (folder / "sub").mkdir(parents=True)
    (folder / "sub" / name).write_text("s")
    assert setup.preview(str(folder)).left_out == [setup.LeftOut(f"sub/{name}", "secret", 1)]


def test_a_folder_too_big(workspace, git_config, monkeypatch):
    monkeypatch.setattr(setup, "MAX_FILES", 3)
    folder = workspace / "many"
    folder.mkdir()
    for n in range(5):
        (folder / f"{n}.txt").write_text("x")
    assert setup.preview(str(folder)).refusal == setup.Refusal("too_big", 4, 4)


def test_a_folder_of_too_many_bytes(workspace, git_config, monkeypatch):
    monkeypatch.setattr(setup, "MAX_BYTES", 5)
    folder = workspace / "heavy"
    folder.mkdir()
    for n in range(3):
        (folder / f"{n}.txt").write_text("abc")
    assert setup.preview(str(folder)).refusal == setup.Refusal("too_big", 2, 6)


def test_the_home_folder_the_root_and_the_workspace_are_refused(workspace, git_config, tmp_path):
    for folder in (Path.home(), Path("/"), workspace, tmp_path):
        assert setup.preview(str(folder)).refusal == setup.Refusal("home", 0, 0)


def test_a_folder_git_cannot_read_is_refused_with_gits_line(workspace, git_config):
    if os.geteuid() == 0:
        pytest.skip("root reads every folder")
    folder = workspace / "locked-in"
    (folder / "locked").mkdir(parents=True)
    (folder / "a.txt").write_text("a")
    (folder / "locked").chmod(0)
    try:
        refusal = setup.preview(str(folder)).refusal
    finally:
        (folder / "locked").chmod(0o755)
    assert refusal.kind == "unreadable"
    assert "could not open directory 'locked/'" in refusal.line


def test_the_command_leaves_out_what_the_preview_does(workspace, git_config):
    folder = workspace / "q"
    folder.mkdir()
    (folder / "my notes.txt").write_text("n")
    assert (
        setup.preview(str(folder)).command
        == "git init && git add -A && git commit -m 'First commit'"
    )
    (folder / ".env").write_text("s")
    (folder / "it's.key").write_text("s")
    assert setup.preview(str(folder)).command == (
        "printf '%s\\n' /.env '/it'\"'\"'s.key' >> .gitignore"
        " && git init && git add -A && git commit -m 'First commit'"
    )  # fmt: skip


def test_make_commits_once_and_ignores_what_it_leaves_out(notes):
    root = setup.make(str(notes), [])
    assert Path(root) == notes.resolve()
    assert git(notes, "log", "--format=%s") == "First commit"
    assert git(notes, "ls-files").splitlines() == [".gitignore", "a.txt"]
    assert (notes / ".gitignore").read_text() == ("/.env\n/big.bin\n/deploy/server.key\n/old/\n")
    assert (notes / ".env").exists()
    assert git(notes, "status", "--porcelain") == ""


def test_make_takes_a_ticked_secret(notes):
    setup.make(str(notes), [".env"])
    assert ".env" in git(notes, "ls-files").splitlines()
    assert "/.env" not in (notes / ".gitignore").read_text().splitlines()


def test_make_appends_to_the_folders_gitignore(notes):
    (notes / ".gitignore").write_text("*.tmp")  # no newline at its end
    setup.make(str(notes), [".env", "big.bin", "deploy/server.key"])
    assert (notes / ".gitignore").read_text() == "*.tmp\n/old/\n"


def test_make_refuses_a_repository_ticked_in(notes):
    with pytest.raises(setup.SetupError) as refused:
        setup.make(str(notes), ["old/"])
    assert refused.value.kind == "bad_include"
    assert not (notes / ".git").exists()


def test_make_refuses_a_folder_too_big(notes, monkeypatch):
    monkeypatch.setattr(setup, "MAX_FILES", 0)
    with pytest.raises(setup.SetupError) as refused:
        setup.make(str(notes), [])
    assert refused.value.kind == "too_big"
    assert not (notes / ".git").exists()


def test_make_needs_gits_author(notes, git_config):
    git_config.write_text("")
    with pytest.raises(setup.SetupError) as refused:
        setup.make(str(notes), [])
    assert refused.value.kind == "no_author"
    assert not (notes / ".git").exists()


def failing_commit(tmp_path, monkeypatch):
    """A git on PATH whose commit fails, as a broken git or a full disk would."""
    real = shutil.which("git")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "git").write_text(
        "#!/bin/sh\n"
        'for arg in "$@"; do\n'
        '  if [ "$arg" = commit ]; then echo "fatal: no commit today" >&2; exit 128; fi\n'
        "done\n"
        f'exec {real} "$@"\n'
    )
    (bin_dir / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


@pytest.mark.parametrize("before", [None, b"*.tmp"])
def test_a_failed_commit_leaves_the_folder_as_it_was(notes, tmp_path, monkeypatch, before):
    if before is not None:
        (notes / ".gitignore").write_bytes(before)
    failing_commit(tmp_path, monkeypatch)
    with pytest.raises(setup.SetupError) as refused:
        setup.make(str(notes), [])
    assert (refused.value.kind, str(refused.value)) == (
        "git_failed",
        f"git could not set up {notes}: fatal: no commit today",
    )
    assert not (notes / ".git").exists()
    if before is None:
        assert not (notes / ".gitignore").exists()
    else:
        assert (notes / ".gitignore").read_bytes() == before


def test_make_refuses_a_repository(notes):
    git(notes, "init", "--quiet")
    with pytest.raises(setup.SetupError) as refused:
        setup.make(str(notes), [])
    assert refused.value.kind == "not_plain"
