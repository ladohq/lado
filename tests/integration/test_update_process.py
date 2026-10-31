"""`lado update` as a process: it stops the running sessions and the UI server, waits for the
sessions' loops, runs the installer, checks the installed version and resumes everything with
the installed `lado`'s public commands. No network and no real uv or pipx: the index is a
local file (LADO_UPDATE_INDEX), the installer a script (LADO_UPDATE_INSTALLER), and the
install's prefix (LADO_UPDATE_PREFIX) has a `bin/lado` that says the version a file holds and
runs this working copy for everything else."""

import json
import os
import subprocess
import sys
import threading
import urllib.request
import uuid

import agent_helpers
import fake_provider
import pytest

from lado import __version__, loop, runtime, state
from lado.server import auth
from lado.server import run as server_run

pytestmark = pytest.mark.integration

NEW = "99.0.0"
OLD = "0.1.0"


@pytest.fixture
def session():
    return f"upd-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def no_server_left():
    yield
    if server_run.running():
        server_run.stop()


class Install:
    """A fake install of LADO: its `bin/lado`, the version it reports, and its installer."""

    def __init__(self, folder):
        self.prefix = folder / "prefix"
        (self.prefix / "bin").mkdir(parents=True)
        self.version_file = folder / "installed-version"
        self.version_file.write_text(__version__)
        self.calls = folder / "calls"
        # The processes of the installed lado say the version it was installed as (the UI
        # server's /api/health too): a sitecustomize on their PYTHONPATH sets it. Under
        # LADO_TEST_SCHEMA (newer_schema) a process is a later LADO, whose migrations to that
        # schema change nothing but the version; installed as OLD it is this one again.
        self.site = site = folder / "site"
        site.mkdir()
        (site / "sitecustomize.py").write_text(
            "import os\n"
            "if os.environ.get('LADO_TEST_VERSION'):\n"
            "    import lado\n"
            "    lado.__version__ = os.environ['LADO_TEST_VERSION']\n"
            "if os.environ.get('LADO_TEST_SCHEMA'):\n"
            "    from lado import state\n"
            "    for version in range(state.SCHEMA_VERSION, int(os.environ['LADO_TEST_SCHEMA'])):\n"
            "        state.MIGRATIONS[version] = []\n"
            "    state.SCHEMA_VERSION = int(os.environ['LADO_TEST_SCHEMA'])\n"
        )
        lado = self.prefix / "bin" / "lado"
        # Every call of the installed lado is written down; `start` and `ui` run this working
        # copy with the fake providers, as `lado` of any version would take them.
        lado.write_text(
            "#!/bin/sh\n"
            f'echo "$*" >> "{self.calls}"\n'
            'if [ "$1" = "--version" ]; then\n'
            f'  echo "lado $(cat "{self.version_file}")"; exit 0\n'
            "fi\n"
            f'export LADO_TEST_VERSION="$(cat "{self.version_file}")" PYTHONPATH="{site}"\n'
            f'[ "$LADO_TEST_VERSION" = "{OLD}" ] && unset LADO_TEST_SCHEMA\n'
            f'exec "{sys.executable}" "{fake_provider.LADO}" "$@"\n'
        )
        lado.chmod(0o755)
        self.installer = folder / "installer"

    def run(self, *args: str) -> subprocess.CompletedProcess:
        """The installed lado itself."""
        return subprocess.run(
            [str(self.prefix / "bin" / "lado"), *args],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            check=False,
            timeout=120,
        )

    def installs(self, script: str) -> None:
        """The installer: a shell script given the version as $1."""
        self.installer.write_text(f"#!/bin/sh\n{script}\n")
        self.installer.chmod(0o755)

    def called(self) -> list[str]:
        return self.calls.read_text().splitlines() if self.calls.exists() else []


def publish(folder, old_schema: int = state.SCHEMA_VERSION) -> None:
    """The index: NEW, this version, and OLD with a wheel that says `old_schema`."""
    old = agent_helpers.wheel(folder / "wheels", old_schema, OLD)
    agent_helpers.write_index(
        folder / "index.json", **{NEW: "2026-10-04", __version__: "2026-10-01", OLD: [old]}
    )


@pytest.fixture
def install(tmp_path, monkeypatch):
    found = Install(tmp_path)
    publish(tmp_path)
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(tmp_path / "index.json"))
    monkeypatch.setenv("LADO_UPDATE_PREFIX", str(found.prefix))
    monkeypatch.setenv("LADO_UPDATE_INSTALLER", str(found.installer))
    found.installs(f'echo "installing lado==$1"; echo "$1" > "{found.version_file}"')
    return found


def lado_cli(*args: str, timeout: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "lado.cli", *args],
        capture_output=True,
        text=True,
        env=os.environ,
        stdin=subprocess.DEVNULL,
        check=False,
        timeout=timeout,
    )


def loops(session: str) -> list[str]:
    found = subprocess.run(
        ["pgrep", "-f", f"lado.cli loop {session}$"], capture_output=True, text=True
    )
    return found.stdout.split()


def start(repo, session: str) -> str:
    """A running session with its loop; the supervisor's instance."""
    runtime.start_session(str(repo), session, None, "fake")
    supervisor_idle(session)
    agent_helpers.wait_for(lambda: len(loops(session)) == 1, "one loop", session)
    return state.get_agent(session, "supervisor").instance


def supervisor_idle(session: str) -> None:
    agent_helpers.wait_for(
        lambda: (a := state.get_agent(session, "supervisor")) and a.status == state.IDLE,
        "the supervisor idle",
        session,
    )


def server() -> dict:
    started = lado_cli("ui", "--no-open", "--port", "0")
    assert started.returncode == 0, started.stderr
    return server_run.running()


def resumed(session: str) -> int:
    return sum(e.kind == state.SESSION_RESUME for e in state.list_events(session))


def test_update_restarts_the_session_and_the_server_on_the_new_version(repo, session, install):
    instance = start(repo, session)
    before = server()
    old_loop = loops(session)
    done = lado_cli("update", "--yes")
    assert done.returncode == 0, done.stdout + done.stderr
    assert f"LADO {__version__} -> {NEW} (PyPI, released 2026-10-04)\n" in done.stdout
    # The server's stop waits for its lock to be free: it is gone before the installer runs.
    assert done.stdout.index(f"Stopping session {session}... stopped") < done.stdout.index(
        "Stopping the UI server... stopped"
    )
    assert done.stdout.index("Stopping the UI server... stopped") < done.stdout.index(
        f"installing lado=={NEW}"
    )
    assert f"Resuming on LADO {NEW}:" in done.stdout
    assert f'Resumed session "{session}" in {repo}' in done.stdout
    assert done.stdout.endswith(f"LADO {NEW} is ready. Reload open UI tabs.\n")
    # Resumed by the installed lado's commands (LADO's own resume waits for a missing
    # login), the server where it was.
    assert install.called() == [
        "--version",
        f"start {repo} --name {session} --no-attach --wait-for-login",
        f"ui --no-open --port {before['port']}",
    ]
    assert resumed(session) == 1
    supervisor_idle(session)
    assert state.get_agent(session, "supervisor").instance != instance
    agent_helpers.wait_for(lambda: len(loops(session)) == 1, "the new loop", session)
    assert loops(session) != old_loop
    after = server_run.running()
    assert (after["host"], after["port"]) == (before["host"], before["port"])
    assert after["pid"] != before["pid"]
    assert not (state.home() / "update.json").exists()


def test_the_installer_runs_after_the_sessions_loop_is_gone(repo, session, install):
    start(repo, session)
    # What the installer sees when it starts: the session stopped, its loop's lock free.
    # (No server: stopping one would give the loop time to end anyway.)
    seen = install.prefix.parent / "seen"
    install.installs(
        f'"{sys.executable}" -c "'
        "from lado import loop, state; "
        f"print(bool(state.get_session('{session}').stopped_at), loop.running('{session}'))"
        f'" > "{seen}"; echo "$1" > "{install.version_file}"'
    )
    done = lado_cli("update", "--yes")
    assert done.returncode == 0, done.stdout + done.stderr
    assert seen.read_text().split() == ["True", "False"]


def test_a_failed_installer_resumes_the_session_on_the_old_version(repo, session, install):
    start(repo, session)
    install.installs("echo 'no space left'; exit 1")
    done = lado_cli("update", "--yes")
    assert done.returncode == 1
    assert (
        f"The upgrade failed; LADO {__version__} is unchanged. Resuming the sessions on it:"
        in done.stdout
    )
    assert resumed(session) == 1
    assert not state.get_session(session).stopped_at
    assert (state.home() / "update.json").exists()  # the sessions are back: says nothing
    assert "did not finish" not in lado_cli("ls").stderr


def test_an_installer_that_installs_another_version_is_named_and_rolled_back(
    repo, session, install
):
    start(repo, session)
    install.installs(
        f'[ "$1" = "{NEW}" ] && echo "{NEW}-broken" > "{install.version_file}" '
        f'|| echo "$1" > "{install.version_file}"'
    )
    done = lado_cli("update", "--yes")
    assert done.returncode == 1
    assert f"The installer finished, but LADO is {NEW}-broken, not {NEW}.\n" in done.stdout
    assert f"Rolling back to LADO {__version__}: " in done.stdout
    assert f"Reinstalling: {install.installer} {__version__}\n" in done.stdout
    assert done.stdout.endswith("Attach with: lado attach " + session + "\n")
    assert resumed(session) == 1
    assert json.loads((state.home() / "update-result.json").read_text())["outcome"] == (
        "rolled_back"
    )


def test_update_back_to_an_older_lado_resumes_with_its_public_commands(repo, session, install):
    """The older lado knows no `lado update`: only `start` and `ui` are asked of it."""
    start(repo, session)
    server()
    backups = state.home() / "backups"
    done = lado_cli("update", OLD, "--yes")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "lado.db" not in done.stderr + done.stdout  # the same schema: nothing to restore
    assert f"Resuming on LADO {OLD}:" in done.stdout
    assert [call.split()[0] for call in install.called()] == ["--version", "start", "ui"]
    assert resumed(session) == 1
    assert server_run.running()
    assert not backups.exists()


def stopped(session: str) -> None:
    runtime.stop_session(session)
    agent_helpers.wait_for(lambda: not loops(session), "the loop gone", session)


def newer_schema(install, monkeypatch) -> int:
    """From now on this LADO, the processes it starts and the installed lado but OLD are a
    later LADO whose schema is one past this one's, reached by a step that changes nothing
    but the version: OLD then knows lado.db up to this one's schema only, and refuses the
    newer one as a real older release does. Its schema."""
    newer = state.SCHEMA_VERSION + 1
    monkeypatch.setenv("PYTHONPATH", str(install.site))
    monkeypatch.setenv("LADO_TEST_SCHEMA", str(newer))
    monkeypatch.setitem(state.MIGRATIONS, state.SCHEMA_VERSION, [])
    monkeypatch.setattr(state, "SCHEMA_VERSION", newer)
    return newer


def test_update_to_an_older_schema_restores_the_migrations_copy_and_the_old_lado_sees_its_session(
    tmp_path, repo, session, install, monkeypatch
):
    old, new = session, f"{session}-new"
    before = state.SCHEMA_VERSION
    start(repo, old)
    stopped(old)
    after = newer_schema(install, monkeypatch)
    migrated = install.run("ls")  # OLD is not installed yet: the later LADO
    assert migrated.returncode == 0, migrated.stderr  # no session runs: it migrates, copy first
    assert state.schema_version() == after
    install.version_file.write_text(OLD)  # OLD really refuses this lado.db
    assert "made by a newer LADO" in install.run("ls").stderr
    install.version_file.write_text(__version__)
    copy = state.home() / "backups" / f"lado.db.schema-{before}"
    kept = copy.read_bytes()
    start(repo, old)
    start(agent_helpers.init_repo(tmp_path / "other"), new)  # not in the copy
    publish(tmp_path, before)
    done = lado_cli("update", OLD, "--yes")
    assert done.returncode == 0, done.stdout + done.stderr
    assert (
        f"lado: WARNING: LADO {OLD} knows lado.db up to schema {before}; lado.db has schema "
        f"{after}.\n  lado.db goes back to {copy}, made "
    ) in done.stderr
    assert f"  Sessions not in that copy are not started again: {new}\n" in done.stderr
    assert f"Restored lado.db from {copy} (schema {before})" in done.stdout
    starts = [call for call in install.called() if call.startswith("start")]
    assert starts == [f"start {repo} --name {old} --no-attach --wait-for-login"]
    assert state.schema_version() == before
    listed = install.run("ls")  # OLD now, which refuses schema `after`
    assert listed.returncode == 0, listed.stderr
    assert old in listed.stdout and new not in listed.stdout
    assert [p.name for p in copy.parent.iterdir()] == [copy.name]
    assert copy.read_bytes() == kept
    result = json.loads((state.home() / "update-result.json").read_text())
    assert (result["outcome"], result["database"]) == ("ok", "restored")


def test_update_to_an_older_schema_without_its_copy_stops_nothing(tmp_path, repo, session, install):
    start(repo, session)
    publish(tmp_path, state.SCHEMA_VERSION - 1)
    done = lado_cli("update", OLD, "--yes")
    assert done.returncode == 1
    assert done.stderr == (
        f"lado: LADO {OLD} needs lado.db at schema {state.SCHEMA_VERSION - 1}, and lado.db has "
        f"schema {state.SCHEMA_VERSION}; {state.home() / 'backups'} holds no "
        f"lado.db.schema-{state.SCHEMA_VERSION - 1} to go back to (docs/install.md, Going back "
        "to an older version); nothing was stopped\n"
    )
    assert install.called() == []
    assert not state.get_session(session).stopped_at
    assert loops(session)


def test_a_session_that_does_not_resume_is_named_and_the_others_resume(
    tmp_path, repo, session, install
):
    other = f"{session}-b"
    start(repo, session)
    start(agent_helpers.init_repo(tmp_path / "other"), other)
    # The second resume fails: its repo is gone by then.
    install.installs(f'echo "$1" > "{install.version_file}"; rm -rf "{tmp_path / "other"}"')
    done = lado_cli("update", "--yes")
    assert done.returncode == 1
    assert (
        f"lado: session {other} did not resume (exit code 1); resume it with "
        f"lado start {tmp_path / 'other'} --name {other}"
    ) in done.stderr
    assert resumed(session) == 1 and resumed(other) == 0
    listed = lado_cli("ls")
    assert (
        f"lado: an update did not finish: sessions {other} may be stopped; resume them with "
        f"lado start {tmp_path / 'other'} --name {other}"
    ) in listed.stderr


def test_the_servers_update_check_holds_up_no_other_request(tmp_path, monkeypatch):
    # Reading a FIFO blocks until the test writes into it: a look at PyPI that hangs.
    fifo = tmp_path / "index.fifo"
    os.mkfifo(fifo)
    monkeypatch.delenv("LADO_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(fifo))
    url = server()["url"]
    headers = {"Authorization": f"Bearer {auth.token()}"}
    checked = {}

    def ask_update():
        request = urllib.request.Request(f"{url}/api/update", headers=headers)
        with urllib.request.urlopen(request, timeout=30) as answer:
            checked.update(json.load(answer))

    def reader() -> int | None:
        """A writing end of the FIFO once the server opened it to read, else None."""
        try:
            return os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
        except OSError:  # ENXIO: no reader yet
            return None

    asking = threading.Thread(target=ask_update)
    asking.start()
    end = agent_helpers.wait_for(reader, "the update request to read the FIFO", "none")
    with urllib.request.urlopen(f"{url}/api/health", timeout=5) as answer:
        assert json.load(answer)["ok"]
    assert asking.is_alive()
    with os.fdopen(end, "w") as index:
        index.write(json.dumps(agent_helpers.pypi_index(**{NEW: "2026-10-04"})))
    asking.join(30)
    assert checked["available"] == NEW


def test_update_at_the_latest_version_stops_nothing(repo, session, install, tmp_path, monkeypatch):
    agent_helpers.write_index(tmp_path / "latest.json", **{__version__: "2026-10-01"})
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(tmp_path / "latest.json"))
    start(repo, session)
    done = lado_cli("update", "--yes")
    assert (done.returncode, done.stdout) == (0, f"LADO {__version__} is the latest version.\n")
    assert not state.get_session(session).stopped_at
    assert loop.running(session)
    assert install.called() == []


def api(url: str, path: str, body: dict | None = None):
    """The server's answer to a GET, or with `body` a POST, as the UI sends them; None while
    it does not answer."""
    request = urllib.request.Request(
        f"{url}{path}",
        data=None if body is None else json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {auth.token()}",
            "Content-Type": "application/json",
            "Origin": url,
        },
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as answer:
            return answer.status, json.load(answer)
    except OSError:
        return None


def update_from_the_ui(url: str) -> tuple[dict, dict, dict]:
    """POST /api/update as the page does, then wait as U2 waits: for a server started after
    the one before, a result of this update that no longer runs and its lock released
    (`running` false: the result is written under the lock). The health before, the health
    after and the UpdateInfo after."""
    before = api(url, "/api/health")[1]
    status, started = api(url, "/api/update", {"to": NEW})
    assert status == 202

    def back():
        health = api(url, "/api/health")
        info = api(url, "/api/update")
        if not health or not info or info[1]["running"]:
            return None
        if health[1]["started_at"] <= before["started_at"]:
            return None
        last = info[1]["last"]
        if not last or last["id"] != started["id"] or last["outcome"] == "running":
            return None
        return health[1], info[1]

    after, info = agent_helpers.wait_for(back, "the server back after the update", "none", 120)
    return before, after, info


def test_the_ui_updates_lado_and_the_server_comes_back_on_the_new_version(repo, session, install):
    start(repo, session)
    url = server()["url"]
    before, after, info = update_from_the_ui(url)
    assert (before["version"], after["version"]) == (__version__, NEW)
    last = info["last"]
    assert (last["outcome"], last["from"], last["to"], last["database"]) == (
        "ok",
        __version__,
        NEW,
        "kept",
    )
    assert last["tail"][-1] == f"LADO {NEW} is ready. Reload open UI tabs."
    assert install.called() == [
        "--version",
        f"start {repo} --name {session} --no-attach --wait-for-login",
        f"ui --no-open --port {server_run.running()['port']}",
    ]
    assert resumed(session) == 1


def test_the_ui_update_rolls_back_when_the_new_version_is_wrong(repo, session, install):
    start(repo, session)
    url = server()["url"]
    install.installs(
        f'[ "$1" = "{NEW}" ] && echo "{NEW}-broken" > "{install.version_file}" '
        f'|| echo "$1" > "{install.version_file}"'
    )
    before, after, info = update_from_the_ui(url)
    assert after["version"] == before["version"] == __version__  # the old one, restarted
    last = info["last"]
    assert last["outcome"] == "rolled_back"
    assert last["reason"] == f"LADO {NEW} did not install right: --version says {NEW}-broken"
    assert resumed(session) == 1
    assert info["running"] is False
