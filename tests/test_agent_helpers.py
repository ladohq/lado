import dataclasses
import os
import shutil
import subprocess
import threading

import agent_helpers
import pytest
from agent_helpers import init_repo

from lado import loop, state, tmux
from lado.providers import base


def _config(repo, key, *scope):
    result = subprocess.run(
        ["git", "-C", str(repo), "config", *scope, "--get", key], capture_output=True, text=True
    )
    return result.stdout.strip()


def test_copies_of_the_template_skip_lock_files_that_vanish(tmp_path, monkeypatch):
    # git's background maintenance holds .git/objects/maintenance.lock in the template for a
    # moment: the copy lists the file, and it is gone when the copy reads it.
    monkeypatch.setattr(agent_helpers, "_template", None)
    init_repo(tmp_path / "first")  # makes a fresh template
    template = agent_helpers._template
    (template / ".git" / "objects" / "maintenance.lock").write_text("")
    copyfile = shutil.copyfile

    def vanishing(src, dst, *args, **kwargs):
        if os.fspath(src).endswith(".lock"):
            (template / ".git" / "objects" / "maintenance.lock").unlink(missing_ok=True)
        return copyfile(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "copyfile", vanishing)
    repo = init_repo(tmp_path / "second")
    assert not (repo / ".git" / "objects" / "maintenance.lock").exists()
    assert _config(repo, "user.name") == "LADO test"


def test_test_repos_never_run_git_maintenance(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_helpers, "_template", None)
    repo = init_repo(tmp_path / "repo")
    # In the repo's own config, so it holds for whatever process runs git there.
    assert _config(repo, "gc.auto", "--local") == "0"
    assert _config(repo, "maintenance.auto", "--local") == "false"
    # And for every other repo the test run makes (bare remotes, kit source clones).
    other = tmp_path / "other.git"
    subprocess.run(["git", "init", "-q", "--bare", str(other)], check=True)
    assert _config(other, "gc.auto") == "0"
    assert _config(other, "maintenance.auto") == "false"


def test_a_run_in_an_agents_shell_drops_what_the_launch_set_but_its_tmpdir():
    launch = "CLAUDE_CODE_TMPDIR,LADO_AGENT,TMPDIR,LADO_MODEL_KEY_GW"
    agent = {
        "LADO_LAUNCH_VARS": launch,
        "CLAUDE_CODE_TMPDIR": "/t/claude",
        "LADO_AGENT": "w1",
        "TMPDIR": "/t/w1",
        "LADO_MODEL_KEY_GW": "secret",
        "LADO_CONTAINER": "1",
        "TMUX": "/tmp/tmux-1/lado,1,0",
        "FOO": "bar",
    }
    assert agent_helpers.without_agent_launch(agent) == {"TMPDIR": "/t/w1", "FOO": "bar"}


def test_a_run_outside_an_agent_drops_only_lados_own_names():
    # CI: no launch, so a variable a launch would set stays as the user set it.
    user = {"LADO_HOME": "/h", "TMUX": "/tmp/tmux-1/default,1,0", "CLAUDE_CODE_TMPDIR": "/c"}
    assert agent_helpers.without_agent_launch(user) == {"CLAUDE_CODE_TMPDIR": "/c"}


@pytest.fixture
def failed_session(lado_home, monkeypatch):
    """Session "s" as a live test leaves it when it fails: w1 busy, its report queued, a hook
    error logged, w1's config written, two tmux windows with something on the screen."""
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    w1 = state.Agent(
        "s",
        "w1",
        "worker",
        "/r/.lado/worktrees/s/w1",
        "lado/s/w1",
        "t",
        state.BUSY,
        provider="claude",
    )
    state.add_agent(w1)
    state.add_agent(dataclasses.replace(w1, name="supervisor", cwd="/r", status=state.IDLE))
    state.add_event("s", "w1", state.STATUS, state.BUSY)
    state.queue_message("s", "w1", "supervisor", "done", "details")
    (lado_home / "hooks.log").write_text("hook error\n")
    (base.config_dir(w1) / "kilo.json").write_text("{}")
    screens = {"supervisor": "supervisor screen\n", "w1": "w1 screen\n"}

    def run(*args, input=None):
        if args[0] == "list-windows":
            return "".join(f"{name}\n" for name in screens)
        if args[0] == "capture-pane":
            return screens[args[-1].split(":")[1].lstrip("=")]
        raise AssertionError(args)

    monkeypatch.setattr(tmux, "run", run)
    return "s"


def test_keep_evidence_copies_log_hooks_config_and_screens(failed_session, tmp_path):
    folder = agent_helpers.keep_evidence(failed_session, tmp_path / "evidence")
    log = (folder / "lado-log.txt").read_text()
    assert "w1: busy" in log
    assert "w1 → supervisor [pending] done\n    details" in log
    assert (folder / "hooks.log").read_text() == "hook error\n"
    assert (folder / "agents" / "w1" / "kilo.json").read_text() == "{}"
    assert (
        "w1 worker busy cwd /r/.lado/worktrees/s/w1 branch lado/s/w1"
        in (folder / "agents.txt").read_text()
    )
    assert (folder / "screens" / "supervisor.txt").read_text() == "supervisor screen\n"
    assert (folder / "screens" / "w1.txt").read_text() == "w1 screen\n"


def test_keep_evidence_of_a_stopped_session_keeps_what_is_left(
    failed_session, tmp_path, monkeypatch
):
    def no_server(*args, input=None):
        raise tmux.TmuxError("no server running")

    monkeypatch.setattr(tmux, "run", no_server)
    state.delete_agent("s", "w1")
    folder = agent_helpers.keep_evidence(failed_session, tmp_path / "evidence")
    assert "w1: busy" in (folder / "lado-log.txt").read_text()
    assert "no server running" in (folder / "screens" / "error.txt").read_text()
    assert (folder / "agents" / "w1" / "kilo.json").exists()


def test_keep_evidence_keeps_links_as_links_and_notes_what_it_cannot_copy(
    failed_session, tmp_path, lado_home
):
    """A Codex agent's config folder is its CODEX_HOME: links into Codex's install, and
    clones Codex changes while the copy runs."""
    home = lado_home / "agents" / "s" / "w1"
    (home / "tmp" / "arg0").mkdir(parents=True)
    (home / "tmp" / "arg0" / "apply_patch").symlink_to("/nowhere/codex")
    (home / "plugins").mkdir()
    (home / "plugins" / "linked").symlink_to(tmp_path)  # a folder
    (home / "plugins" / "locked.json").write_text("{}")
    (home / "plugins" / "locked.json").chmod(0)
    try:
        folder = agent_helpers.keep_evidence(failed_session, tmp_path / "evidence")
    finally:
        (home / "plugins" / "locked.json").chmod(0o600)
    kept = folder / "agents" / "w1"
    assert os.readlink(kept / "tmp" / "arg0" / "apply_patch") == "/nowhere/codex"
    assert os.readlink(kept / "plugins" / "linked") == str(tmp_path)
    assert (kept / "kilo.json").read_text() == "{}"
    note = (folder / "agents-not-copied.txt").read_text()
    assert "locked.json" in note
    assert (folder / "screens" / "w1.txt").exists()  # the rest goes on


def test_keep_evidence_redacts_the_secrets_it_is_given(failed_session, tmp_path, lado_home):
    secret = "sk-the-key-of-the-endpoint"
    (lado_home / "hooks.log").write_text(f"error with {secret} in it\n")
    (lado_home / "agents" / "s" / "w1" / "env.json").write_text(f'{{"KEY": "{secret}"}}')
    folder = agent_helpers.keep_evidence(failed_session, tmp_path / "evidence", (secret,))
    kept = [p for p in folder.rglob("*") if p.is_file()]
    assert not [p for p in kept if secret.encode() in p.read_bytes()]
    assert "error with <redacted> in it" in (folder / "hooks.log").read_text()
    assert (folder / "agents" / "w1" / "kilo.json").read_text() == "{}"


def test_a_timed_out_wait_says_what_it_waited_for_and_the_last_state(failed_session):
    with pytest.raises(pytest.fail.Exception) as failed:
        agent_helpers.wait_for(lambda: False, "w1's report", failed_session, timeout=0)
    first = str(failed.value).splitlines()[0]
    assert first.startswith("timed out after 0s waiting for w1's report; ")
    assert "agents: w1 busy" in first
    assert "messages: w1 → supervisor [pending] 'done'" in first


@pytest.fixture
def worker(lado_home):
    """Session "s" with an idle worker w1 and the supervisor."""
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    w1 = state.Agent("s", "w1", "worker", "/r", "lado/s/w1", "t", state.IDLE, provider="claude")
    state.add_agent(w1)
    state.add_agent(dataclasses.replace(w1, name="supervisor"))
    return "w1"


def test_an_idle_agent_with_no_messages_is_settled(worker):
    assert agent_helpers.settled("s", worker)


def test_a_busy_agent_is_not_settled(worker):
    state.set_status("s", worker, state.BUSY)
    assert not agent_helpers.settled("s", worker)


@pytest.mark.parametrize("mark", [state.PENDING, state.SENT])
def test_an_idle_agent_with_a_message_still_to_come_is_not_settled(worker, mark):
    # A turn-end reminder is queued before the agent turns idle; a typed one is sent until
    # the next turn's hook confirms it.
    state.queue_message(
        "s", state.LADO, worker, "your answer went only to your terminal", mark=mark
    )
    assert not agent_helpers.settled("s", worker)


def test_an_idle_agent_whose_messages_were_all_taken_is_settled(worker):
    state.queue_message("s", "human", worker, "advance r done", mark=state.DELIVERED)
    state.queue_message("s", "supervisor", worker, "read it", "a body", mark=state.DELIVERED)
    state.queue_message("s", "supervisor", worker, "done", "read", mark=state.READ)
    # Messages to others do not count.
    state.queue_message("s", state.LADO, "supervisor", "a step")
    assert agent_helpers.settled("s", worker)


@pytest.mark.parametrize("reason", [loop.STOPPED, loop.TMUX_GONE])
def test_a_loop_ended_by_lado_stop_ends_with_either_stop_reason(lado_home, reason):
    # `lado stop` kills the tmux session, then marks the session stopped: the loop may see
    # either first.
    loop.log("s", "loop started, pid 1")
    loop.log("other", "loop ended: the session is gone")
    loop.log("s", f"loop ended: {reason}")
    agent_helpers.check_loop_ended_by_stop("s")


@pytest.mark.parametrize("logged", ["loop started, pid 1", "loop ended: the session is gone"])
def test_a_loop_not_ended_by_lado_stop_fails_the_check(lado_home, logged):
    loop.log("other", f"loop ended: {loop.STOPPED}")
    loop.log("s", logged)
    with pytest.raises(pytest.fail.Exception, match="s: "):
        agent_helpers.check_loop_ended_by_stop("s")


SECRET = "smoke-refused-key-0123456789"


def test_the_db_scan_passes_without_side_files_and_with_a_clean_lado_db(tmp_path):
    (tmp_path / "lado.db").write_bytes(b"rows without the key")
    agent_helpers.check_no_secret_in_db(tmp_path, SECRET)


def test_the_db_scan_fails_without_lado_db(tmp_path):
    (tmp_path / "lado.db-wal").write_bytes(b"pages")
    with pytest.raises(FileNotFoundError, match="lado.db"):
        agent_helpers.check_no_secret_in_db(tmp_path, SECRET)


@pytest.mark.parametrize("name", ["lado.db-wal", "lado.db-shm", "lado.db"])
def test_the_db_scan_fails_naming_the_file_that_holds_the_secret(tmp_path, name):
    for file in ("lado.db-wal", "lado.db-shm", "lado.db"):
        (tmp_path / file).write_bytes(b"clean")
    (tmp_path / name).write_bytes(f"page with {SECRET} in it".encode())
    with pytest.raises(AssertionError, match=f"{name}$"):
        agent_helpers.check_no_secret_in_db(tmp_path, SECRET)


def test_the_db_scan_reads_the_wal_checkpointed_away_mid_scan_through_lado_db(
    tmp_path, monkeypatch
):
    # The last connection closes as the scan starts: SQLite moves the WAL into lado.db and
    # deletes lado.db-wal and lado.db-shm, so the WAL's read fails and its key is in lado.db.
    db, wal, shm = (tmp_path / n for n in ("lado.db", "lado.db-wal", "lado.db-shm"))
    db.write_bytes(b"clean")
    wal.write_bytes(f"page with {SECRET}".encode())
    shm.write_bytes(b"index")
    read_bytes = type(db).read_bytes

    def checkpointed(path):
        if path.name == "lado.db-wal" and wal.exists():
            db.write_bytes(read_bytes(db) + read_bytes(wal))
            wal.unlink()
            shm.unlink()
        return read_bytes(path)

    monkeypatch.setattr(type(db), "read_bytes", checkpointed)
    with pytest.raises(AssertionError, match="lado.db$"):
        agent_helpers.check_no_secret_in_db(tmp_path, SECRET)


def test_ended_is_true_once_a_process_ends_a_moment_after_the_call():
    sleeper = subprocess.Popen(["sleep", "60"])
    killer = threading.Timer(0.2, sleeper.kill)
    killer.start()
    try:
        assert agent_helpers.ended(sleeper.pid)
    finally:
        killer.join()
        sleeper.kill()
        sleeper.wait()


def test_ended_is_false_when_the_process_outlives_the_timeout():
    sleeper = subprocess.Popen(["sleep", "60"])
    try:
        assert not agent_helpers.ended(sleeper.pid, timeout=0.3)
    finally:
        sleeper.kill()
        sleeper.wait()
