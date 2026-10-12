"""lado.clone: a repository from its git URL (openspec change clone-from-url)."""

import subprocess
import threading
import time
from pathlib import Path

import pytest
from agent_helpers import bare_remote, fake_git, fake_git_calls, gone, init_repo

from lado import clone, runtime


@pytest.mark.parametrize(
    "source",
    [
        "https://github.com/ladohq/lado",
        "http://git.example.com/a/b.git",
        "ssh://git@host:2222/a/b.git",
        "git://host/a/b",
        "file:///srv/app.git",
        "git@github.com:ladohq/lado.git",
    ],
)
def test_a_git_url(source):
    assert clone.is_url(source)


@pytest.mark.parametrize(
    "source", ["~/projects/app", "app", "/srv/app.git", "host:path", "C:/x", ".", ""]
)
def test_a_folder(source):
    assert not clone.is_url(source)


def test_default_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert clone.default_folder("https://github.com/ladohq/marketplace.git/") == (
        tmp_path / "lado" / "marketplace"
    )
    assert clone.default_folder("git@github.com:ladohq/lado.git") == tmp_path / "lado" / "lado"
    assert clone.default_folder("file:///srv/app.git") == tmp_path / "lado" / "app"


def test_address_parts():
    ssh = clone.Address.parse("ssh://deploy@Git.Example.com:2222/~/team/app.git")
    assert (ssh.scheme, ssh.user, ssh.host, ssh.port) == ("ssh", "deploy", "git.example.com", 2222)
    assert (ssh.repo_name, ssh.owner) == ("app", "team")
    scp = clone.Address.parse("git@github.com:ladohq/lado.git")
    assert (scp.scheme, scp.user, scp.host, scp.port) == ("ssh", "git", "github.com", None)
    assert (scp.repo_name, scp.owner) == ("lado", "ladohq")
    https = clone.Address.parse("https://ghp_x@github.com/acme/app")
    assert (https.user, https.host, https.repo_name, https.owner) == (
        "ghp_x",
        "github.com",
        "app",
        "acme",
    )
    assert clone.Address.parse("https://host/app").owner is None


SAME = [
    ("git@github.com:ladohq/lado.git", "https://github.com/ladohq/lado"),
    ("https://github.com/ladohq/lado.git", "ssh://git@github.com:22/ladohq/lado"),
    ("https://GitHub.com/ladohq/lado/", "git://github.com/ladohq/lado.git"),
    ("ssh://git@host/~/team/app.git", "git@host:team/app"),
    ("https://user:pw@host/a/b", "https://host/a/b"),
]
OTHER = [
    ("git@github.com:acme/app.git", "git@github.com:ladohq/app.git"),
    ("https://github.com/ladohq/lado", "https://gitlab.com/ladohq/lado"),
    ("https://github.com/ladohq/lado", "file:///srv/lado"),
]


@pytest.mark.parametrize(("one", "other"), SAME)
def test_the_same_repository_over_another_protocol(one, other):
    assert clone.Address.parse(one).same_repo(clone.Address.parse(other))
    assert clone.Address.parse(other).same_repo(clone.Address.parse(one))


@pytest.mark.parametrize(("one", "other"), OTHER)
def test_another_repository(one, other):
    assert not clone.Address.parse(one).same_repo(clone.Address.parse(other))


def test_local_repositories_compare_by_real_path(tmp_path):
    (tmp_path / "app.git").mkdir()
    (tmp_path / "link.git").symlink_to(tmp_path / "app.git")
    url = clone.Address.parse(f"file://{tmp_path}/app.git")
    assert url.same_repo(clone.Address.parse(f"file://{tmp_path}/link.git"))
    assert url.same_repo(clone.Address.parse(str(tmp_path / "link.git")))
    assert not url.same_repo(clone.Address.parse(f"file://{tmp_path}/other.git"))


def _with_origin(path: Path, origin: str | None) -> Path:
    init_repo(path)
    if origin:
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin", origin], check=True)
    return path


def _listing(path: Path) -> list[tuple[str, int]]:
    return sorted((str(p), p.stat().st_mtime_ns) for p in [path, *path.rglob("*")])


def test_a_new_folder(tmp_path):
    target = clone.check_target("https://github.com/ladohq/lado", str(tmp_path / "lado"))
    assert (target.state, target.text) == ("new", "a new folder")
    assert not (tmp_path / "lado").exists()


def test_an_empty_folder(tmp_path):
    (tmp_path / "lado").mkdir()
    target = clone.check_target("https://github.com/ladohq/lado", str(tmp_path / "lado"))
    assert (target.state, target.text) == ("empty", "an empty folder")


def test_a_clone_of_the_same_repository(tmp_path):
    folder = _with_origin(tmp_path / "lado", "git@github.com:ladohq/lado.git")
    before = _listing(folder)
    target = clone.check_target("https://github.com/ladohq/lado", str(folder))
    assert target.state == "same_repo"
    assert target.text == (
        f"{folder} is already a clone of this repository "
        "(origin git@github.com:ladohq/lado.git), on branch main"
    )
    assert (target.origin, target.branch) == ("git@github.com:ladohq/lado.git", "main")
    assert _listing(folder) == before


def test_another_repository_with_the_same_name(tmp_path):
    folder = _with_origin(tmp_path / "app", "git@github.com:acme/app.git")
    before = _listing(folder)
    target = clone.check_target("git@github.com:ladohq/app.git", str(folder))
    assert target.state == "other_repo"
    assert target.suggestion == str(tmp_path / "ladohq-app")
    assert target.text == (
        f"{folder} is a clone of another repository (origin git@github.com:acme/app.git): "
        f"choose another folder, e.g. {tmp_path / 'ladohq-app'}"
    )
    assert _listing(folder) == before


def test_no_suggestion_when_that_folder_is_taken_or_there_is_no_owner(tmp_path):
    folder = _with_origin(tmp_path / "app", "https://ghp_secret@github.com/acme/app")
    (tmp_path / "ladohq-app").mkdir()
    target = clone.check_target("git@github.com:ladohq/app.git", str(folder))
    assert (target.state, target.suggestion) == ("other_repo", None)
    assert target.text.endswith("(origin https://github.com/acme/app): choose another folder")
    assert "ghp_secret" not in target.text + str(target.origin)
    target = clone.check_target("https://host/app", str(folder))
    assert (target.state, target.suggestion) == ("other_repo", None)


def test_a_folder_with_other_files(tmp_path):
    folder = tmp_path / "app"
    folder.mkdir()
    (folder / "notes.txt").write_text("mine")
    before = _listing(folder)
    target = clone.check_target("https://github.com/acme/app", str(folder))
    assert target.state == "not_empty"
    assert target.text == (
        f"{folder} is not empty and is not a clone of https://github.com/acme/app: "
        "choose another folder"
    )
    assert _listing(folder) == before


def test_a_subfolder_of_a_repository_or_one_without_origin_is_not_empty(tmp_path):
    repo = _with_origin(tmp_path / "app", "https://github.com/acme/app")
    (repo / "sub").mkdir()
    (repo / "sub" / "x").write_text("x")
    assert clone.check_target("https://github.com/acme/app", str(repo / "sub")).state == (
        "not_empty"
    )
    bare = _with_origin(tmp_path / "bare", None)
    assert clone.check_target("https://github.com/acme/bare", str(bare)).state == "not_empty"


def test_a_file(tmp_path):
    (tmp_path / "app").write_text("x")
    target = clone.check_target("https://github.com/acme/app", str(tmp_path / "app"))
    assert (target.state, target.text) == (
        "not_folder",
        f"{tmp_path / 'app'} is a file, not a folder",
    )


KIND_LINES = [
    (
        "git@github.com: Permission denied (publickey).\n"
        "fatal: Could not read from remote repository.\n",
        "ssh_denied",
    ),
    ("Host key verification failed.\nfatal: Could not read from remote repository.", "host_key"),
    (
        "fatal: could not read Username for 'https://github.com': terminal prompts disabled",
        "login_needed",
    ),
    ("remote: Invalid username or password.\nfatal: Authentication failed for 'x'", "login_needed"),
    ("ERROR: Repository not found.\nfatal: Could not read from remote repository.", "not_found"),
    ("remote: Repository not found.\nfatal: repository 'https://x/a/b/' not found", "not_found"),
    ("fatal: '/x' does not appear to be a git repository", "not_found"),
    (
        "ssh: Could not resolve hostname nohost: nodename nor servname provided, or not known",
        "unreachable",
    ),
    ("fatal: unable to access 'https://x/': Could not resolve host: x", "unreachable"),
    ("ssh: connect to host h port 22: Connection refused", "unreachable"),
    ("ssh: connect to host h port 22: Operation timed out", "unreachable"),
    (
        "warning: Could not find remote branch dev to clone.\n"
        "fatal: Remote branch dev not found in upstream origin",
        "no_branch",
    ),
    ("fatal: something else entirely", "git_failed"),
]


@pytest.mark.parametrize(("stderr", "kind"), KIND_LINES)
def test_each_failure_kind_by_gits_words(stderr, kind):
    assert clone.failure("clone", "git@github.com:acme/app.git", stderr, "dev").kind == kind


def test_an_ssh_key_the_host_refuses():
    error = clone.failure("list", "git@github.com:acme/app.git", KIND_LINES[0][0])
    assert str(error) == (
        "cannot read git@github.com:acme/app.git: github.com refused this machine's ssh key "
        "(fatal: Could not read from remote repository.)"
    )
    assert error.hint == runtime.Hint(
        "Check that this machine's ssh key is added to your account on github.com:",
        "ssh -T git@github.com",
    )


def test_an_unknown_host_key_with_a_port_and_a_user():
    error = clone.failure("clone", "ssh://deploy@git.example.com:2222/a/b", KIND_LINES[1][0])
    assert str(error).startswith(
        "cannot clone ssh://deploy@git.example.com:2222/a/b: this machine does not know "
        "git.example.com's ssh host key yet ("
    )
    assert error.hint == runtime.Hint(
        "Connect once in a terminal and accept the host key:",
        "ssh -T -p 2222 deploy@git.example.com",
    )


def test_a_private_https_repository_without_a_login():
    error = clone.failure("clone", "https://github.com/acme/private", KIND_LINES[2][0])
    assert str(error) == (
        "cannot clone https://github.com/acme/private: github.com asks for a login "
        "(fatal: could not read Username for 'https://github.com': terminal prompts disabled)"
    )
    assert error.hint == runtime.Hint("Log in with GitHub's CLI on this machine:", "gh auth login")
    other = clone.failure("clone", "https://git.example.com/a/b", KIND_LINES[2][0])
    assert (
        "git.example.com asks for a login; set up a git credential helper for it on this "
        "machine (" in str(other)
    )
    assert other.hint is None


def test_a_repository_github_does_not_show():
    error = clone.failure("list", "git@github.com:acme/app.git", KIND_LINES[4][0])
    assert str(error) == (
        "cannot read git@github.com:acme/app.git: no repository there, or this machine's "
        "account cannot read it (ERROR: Repository not found.)"
    )
    assert error.hint == runtime.Hint(
        "See which GitHub account this machine uses:", "gh auth status"
    )
    assert clone.failure("list", "https://gitlab.com/a/b", KIND_LINES[4][0]).hint is None


def test_unreachable_no_branch_and_other_failures_have_no_hint():
    unreachable = clone.failure("clone", "https://x/a/b", KIND_LINES[8][0])
    assert str(unreachable) == (
        "cannot clone https://x/a/b: x cannot be reached "
        "(fatal: unable to access 'https://x/': Could not resolve host: x)"
    )
    no_branch = clone.failure("clone", "https://x/a/b", KIND_LINES[11][0], "dev")
    assert str(no_branch) == (
        "cannot clone https://x/a/b: no branch dev "
        "(fatal: Remote branch dev not found in upstream origin)"
    )
    other = clone.failure("clone", "https://x/a/b", "hint: something\nlast words")
    assert str(other) == "cannot clone https://x/a/b: last words"
    assert (unreachable.hint, no_branch.hint, other.hint) == (None, None, None)


def test_a_token_in_the_url_is_never_shown():
    url = "https://ghp_secret@github.com/acme/app"
    stderr = (
        "fatal: unable to access 'https://ghp_secret@github.com/acme/app/': Could not resolve host"
    )
    error = clone.failure("clone", url, stderr)
    assert "https://github.com/acme/app" in str(error)
    assert "ghp_secret" not in str(error)


def test_git_runs_with_no_terminal_and_no_prompt(tmp_path, monkeypatch):
    for key, value in fake_git(tmp_path, "fail").items():
        monkeypatch.setenv(key, value)
    with pytest.raises(clone.CloneError):
        clone.list_branches("https://github.com/acme/app")
    [call] = fake_git_calls(tmp_path)
    assert call["args"][0] == "ls-remote"
    assert call["sid"] == call["pid"]  # a session, and so a process group, of its own
    assert call["tty"] is False
    env = call["env"]
    assert (env["GIT_TERMINAL_PROMPT"], env["SSH_ASKPASS_REQUIRE"]) == ("0", "never")
    assert (env["GCM_INTERACTIVE"], env["LC_ALL"]) == ("never", "C")
    assert "GIT_SSH_COMMAND" not in env


def test_no_git(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(clone.CloneError) as refused:
        clone.list_branches("https://github.com/acme/app")
    assert refused.value.kind == "no_git"
    assert refused.value.hint is not None


def test_branches_and_the_default_one(tmp_path):
    remote = clone.list_branches(bare_remote(tmp_path))
    assert remote.branches == ["main", "develop", "release/1.2"]
    assert remote.default == "main"


def test_an_empty_repository(tmp_path):
    subprocess.run(["git", "init", "-q", "--bare", str(tmp_path / "empty.git")], check=True)
    with pytest.raises(clone.CloneError) as refused:
        clone.list_branches((tmp_path / "empty.git").as_uri())
    assert str(refused.value).endswith(": the repository has no branches yet")


def test_a_remote_that_is_not_there(tmp_path):
    with pytest.raises(clone.CloneError) as refused:
        clone.list_branches((tmp_path / "nothing.git").as_uri())
    assert refused.value.kind == "not_found"


def test_a_remote_that_does_not_answer(tmp_path, monkeypatch):
    for key, value in fake_git(tmp_path, "slow").items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(clone, "LIST_TIMEOUT", 0.5)
    started = time.monotonic()
    with pytest.raises(clone.CloneError) as refused:
        clone.list_branches("https://git.example.com/a/b")
    assert time.monotonic() - started < 5
    assert str(refused.value) == (
        "cannot read https://git.example.com/a/b: git.example.com did not answer within 0.5 s"
    )
    [call] = fake_git_calls(tmp_path)
    assert gone(call["pid"]) and gone(call["child"])


def _branch(folder: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(folder), "symbolic-ref", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _leftovers(parent: Path) -> list[str]:
    return [p.name for p in parent.iterdir() if ".clone-" in p.name]


def test_a_clone_of_a_branch_lands_in_the_target(tmp_path):
    url = bare_remote(tmp_path)
    target = tmp_path / "deep" / "er" / "app"
    assert clone.clone(url, str(target), "develop") == str(target)
    assert _branch(target) == "develop"
    assert runtime.remote(str(target)) == url
    log = subprocess.run(
        ["git", "-C", str(target), "log", "--format=%s"], capture_output=True, text=True
    ).stdout.split()
    assert log == ["develop", "init"]  # all its history
    assert _leftovers(target.parent) == []


def test_a_clone_without_a_branch_takes_the_default_one_into_an_empty_folder(tmp_path):
    url = bare_remote(tmp_path)
    (tmp_path / "app").mkdir()
    clone.clone(url, str(tmp_path / "app"))
    assert _branch(tmp_path / "app") == "main"
    assert _leftovers(tmp_path) == []


def test_a_branch_that_is_not_there(tmp_path):
    url = bare_remote(tmp_path)
    with pytest.raises(clone.CloneError) as refused:
        clone.clone(url, str(tmp_path / "app"), "dev")
    assert refused.value.kind == "no_branch"
    assert f"cannot clone {url}: no branch dev (" in str(refused.value)
    assert not (tmp_path / "app").exists()
    assert _leftovers(tmp_path) == []


def test_a_folder_that_may_not_take_a_clone_is_refused_before_git(tmp_path, monkeypatch):
    for key, value in fake_git(tmp_path / "fake", "ok").items():
        monkeypatch.setenv(key, value)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "mine.txt").write_text("x")
    with pytest.raises(clone.CloneError) as refused:
        clone.clone("https://github.com/acme/app", str(tmp_path / "app"))
    assert refused.value.kind == "not_empty"
    assert fake_git_calls(tmp_path / "fake") == []
    assert sorted(p.name for p in (tmp_path / "app").iterdir()) == ["mine.txt"]


def _cancel_after_first_progress(seen, cancelled):
    def on_progress(progress):
        seen.append(progress)
        cancelled.set()

    return on_progress


def test_cancel_during_the_clone(tmp_path, monkeypatch):
    for key, value in fake_git(tmp_path / "fake", "slow").items():
        monkeypatch.setenv(key, value)
    seen, cancelled = [], threading.Event()
    started = time.monotonic()
    with pytest.raises(clone.CloneError) as refused:
        clone.clone(
            "https://github.com/acme/app",
            str(tmp_path / "app"),
            "dev",
            _cancel_after_first_progress(seen, cancelled),
            cancelled,
        )
    assert time.monotonic() - started < 5
    assert refused.value.kind == "cancelled"
    assert str(refused.value) == "the clone of https://github.com/acme/app was cancelled"
    assert seen[0] == clone.Progress(
        "Receiving objects",
        0,
        "1.00 MiB | 2.00 MiB/s",
        "Receiving objects:  0% (0/100), 1.00 MiB | 2.00 MiB/s",
    )
    [call] = fake_git_calls(tmp_path / "fake")
    assert call["args"][:5] == ["clone", "--progress", "--no-recurse-submodules", "--branch", "dev"]
    assert gone(call["pid"]) and gone(call["child"])
    assert not (tmp_path / "app").exists()
    assert _leftovers(tmp_path) == []


def test_ctrl_c_during_the_clone_cleans_up_alike(tmp_path, monkeypatch):
    for key, value in fake_git(tmp_path / "fake", "slow").items():
        monkeypatch.setenv(key, value)

    def interrupted(progress):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        clone.clone("https://github.com/acme/app", str(tmp_path / "app"), None, interrupted)
    [call] = fake_git_calls(tmp_path / "fake")
    assert gone(call["pid"]) and gone(call["child"])
    assert not (tmp_path / "app").exists()
    assert _leftovers(tmp_path) == []


def test_a_target_filled_during_the_clone(tmp_path, monkeypatch):
    for key, value in fake_git(tmp_path / "fake", "ok").items():
        monkeypatch.setenv(key, value)

    def meanwhile(progress):
        (tmp_path / "app").mkdir(exist_ok=True)
        (tmp_path / "app" / "theirs.txt").write_text("x")

    with pytest.raises(clone.CloneError) as refused:
        clone.clone("https://github.com/acme/app", str(tmp_path / "app"), None, meanwhile)
    assert refused.value.kind == "not_empty"
    assert sorted(p.name for p in (tmp_path / "app").iterdir()) == ["theirs.txt"]
    assert _leftovers(tmp_path) == []


@pytest.mark.parametrize(
    ("line", "progress"),
    [
        (
            "Receiving objects:  45% (450/1000), 12.30 MiB | 2.10 MiB/s",
            ("Receiving objects", 45, "12.30 MiB | 2.10 MiB/s"),
        ),
        ("remote: Counting objects: 100% (3/3), done.", ("Counting objects", 100, "done.")),
        ("Resolving deltas:  12% (1/8)", ("Resolving deltas", 12, "")),
        ("Updating files: 100% (12/12), done.", ("Updating files", 100, "done.")),
        ("Cloning into 'app'...", None),
        ("remote: Enumerating objects: 5, done.", None),
    ],
)
def test_progress_lines(line, progress):
    parsed = clone.parse_progress(line)
    if progress is None:
        assert parsed is None
    else:
        assert (parsed.phase, parsed.percent, parsed.detail) == progress
        assert parsed.line == line


@pytest.fixture
def locked(tmp_path):
    """A folder no one may read or enter, and one that may be read but not written."""
    closed, read_only = tmp_path / "closed", tmp_path / "read-only"
    closed.mkdir()
    read_only.mkdir()
    closed.chmod(0o000)
    read_only.chmod(0o555)
    yield closed, read_only
    closed.chmod(0o755)
    read_only.chmod(0o755)


def test_a_folder_that_cannot_be_read_is_refused_not_raised(locked):
    closed, _ = locked
    for path in (closed, closed / "app"):
        with pytest.raises(clone.CloneError) as refused:
            clone.check_target("https://h/a/app", str(path))
        assert refused.value.kind == "no_access"
        assert str(refused.value).startswith(f"cannot look at {path}: ")


def test_a_folder_that_cannot_be_written_is_refused_not_raised(locked, tmp_path):
    _, read_only = locked
    url = bare_remote(tmp_path)
    with pytest.raises(clone.CloneError) as refused:
        clone.clone(url, str(read_only / "app"))
    assert refused.value.kind == "no_access"
    assert str(refused.value).startswith(f"cannot make a folder in {read_only}: ")


@pytest.mark.parametrize("url", ["https://example.com/", "file:///", "git@host:.git"])
def test_a_url_that_names_no_repository_has_no_default_folder(url, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(clone.CloneError) as refused:
        clone.default_folder(url)
    assert refused.value.kind == "no_repo_name"
    assert str(refused.value) == f"{url} names no repository: give the folder to clone into"
