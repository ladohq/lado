import json
import os
import shutil
import subprocess
import uuid

import leftovers
import pytest
from agent_helpers import init_repo, no_maintenance_env, write_index

# `--shard K/N`: CI's integration and UI shards (tests/shard.py).
from shard import pytest_addoption, pytest_collection_modifyitems, pytest_configure  # noqa: F401

# Tests never use the user's LADO tmux server (socket "lado").
TEST_SOCKET = f"lado-test-{uuid.uuid4().hex[:8]}"

# An agent's shell has these set (its session, its LADO home, its tmux): the tests run there
# as is, and nothing of theirs reaches the agent's LADO, also not from a subprocess. LADO's
# image sets LADO_CONTAINER, LADO_REPOS and LADO_ENV_DIR, compose LADO_LISTEN and
# LADO_PUBLIC_HOST: a test that wants one sets it itself.
for _var in (
    "LADO_AGENT",
    "LADO_SESSION",
    "LADO_HOME",
    "LADO_TMUX_SOCKET",
    "TMUX",
    "LADO_CONTAINER",
    "LADO_REPOS",
    "LADO_ENV_DIR",
    "LADO_LISTEN",
    "LADO_PUBLIC_HOST",
):
    os.environ.pop(_var, None)

# No git command of the test run (the tests', LADO's, the agents') starts background gc or
# maintenance, which would still be writing in a repo while a test copies or removes it.
os.environ.update(no_maintenance_env(os.environ))

# Agents get the test run's environment (the settings above, and in the integration tests
# their short LADO_LOOP_INTERVAL and LADO_RETRY_DELAYS from tests/integration/conftest.py),
# not the user's login shell; tests of the shell set their own.
os.environ["LADO_AGENT_ENV"] = "inherit"

# No test looks up LADO's latest version on PyPI; the tests of the check switch it on with a
# local index (LADO_UPDATE_INDEX).
os.environ["LADO_NO_UPDATE_CHECK"] = "1"

# No test sends usage statistics or errors (lado.telemetry); the tests of sending switch it
# on with telemetry_on, and send only to a local endpoint (telemetry_endpoint). _no_statistics
# checks both for every test.
os.environ["LADO_TELEMETRY"] = "0"
os.environ.pop("DO_NOT_TRACK", None)
os.environ.pop("LADO_TELEMETRY_URL", None)

# No test opens a browser (`lado bug-report`'s y): webbrowser runs `true <url>`, which does
# nothing, also in a test that forgot to replace webbrowser.open (test_cli_bug_report.py
# checks it is set).
os.environ["BROWSER"] = "true"

# On a Mac, the test run is taken for one in the graphical session, wherever it runs (over
# ssh too): no test starts LADO's tmux server through launchd unless it says so
# (lado.gui_session; its own tests and the integration test of launchd set their place).
os.environ["LADO_MACOS_PLACE"] = "gui"

# Every process this pytest process starts carries its pid (each xdist worker its own): a
# run's start reaps what a dead one left, a run's end fails on what it left (tests/leftovers.py).
os.environ["LADO_TEST_PID"] = str(os.getpid())


# Every process started during a test, its fixtures' included, carries the test's node id:
# the run's end names the test that left a process (tests/leftovers.py).
@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item, nextitem):
    os.environ["LADO_TEST_ID"] = item.nodeid
    try:
        return (yield)
    finally:
        os.environ.pop("LADO_TEST_ID", None)


def pytest_sessionstart(session):
    # The controller of an xdist run, or a run without workers; the workers start with it.
    if not hasattr(session.config, "workerinput"):
        leftovers.reap_dead_runs()


_LEFT_BY_WORKERS: list[str] = []


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error):
    _LEFT_BY_WORKERS.append(getattr(node, "workeroutput", {}).get("leftovers", ""))


@pytest.hookimpl(wrapper=True)
def pytest_sessionfinish(session):
    # A worker hands what it left to the controller (xdist sends its output after this
    # hook); the controller checks its own after xdist has stopped the workers, which carry
    # its mark.
    if hasattr(session.config, "workerinput"):
        session.config.workeroutput["leftovers"] = leftovers.describe(leftovers.own_left())
        return (yield)
    result = yield
    left = [leftovers.describe(leftovers.own_left()), *_LEFT_BY_WORKERS]
    if any(left):
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        text = "\n".join(lines for lines in left if lines)
        if reporter:
            reporter.write_sep("=", "processes left by the test run, killed", red=True)
            reporter.write_line(text)
        else:
            print(f"processes left by the test run, killed:\n{text}")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    return result


def _kill_tmux_server(socket: str) -> None:
    if shutil.which("tmux"):
        subprocess.run(["tmux", "-L", socket, "kill-server"], capture_output=True, check=False)
    # tmux leaves the socket file behind.
    (leftovers.tmux_folder() / socket).unlink(missing_ok=True)


@pytest.fixture(scope="session")
def kill_tmux_server():
    return _kill_tmux_server


@pytest.fixture(scope="session", autouse=True)
def _kill_test_tmux_server():
    yield
    _kill_tmux_server(TEST_SOCKET)


@pytest.fixture(autouse=True)
def lado_home(tmp_path, monkeypatch):
    home = tmp_path / "lado-home"
    monkeypatch.setenv("LADO_HOME", str(home))
    monkeypatch.setenv("LADO_TMUX_SOCKET", TEST_SOCKET)
    return home


@pytest.fixture(autouse=True)
def _test_workspace(tmp_path, monkeypatch):
    """The default workspace (no LADO_REPOS) is in tmp_path, never the user's ~/workspace,
    which lado doctor would write a probe in; not made. A test of the ~/workspace default
    takes home_workspace."""
    from lado import projects

    monkeypatch.setattr(projects, "DEFAULT_WORKSPACE", str(tmp_path / "default-workspace"))


@pytest.fixture
def home_workspace(monkeypatch):
    """The default workspace as shipped, ~/workspace: the test points HOME into tmp_path."""
    from lado import projects

    monkeypatch.setattr(projects, "DEFAULT_WORKSPACE", "~/workspace")


@pytest.fixture(autouse=True)
def _no_statistics(request, lado_home):
    """Every test runs with sending off by LADO_TELEMETRY=0 (set above), and leaves nothing
    sent or queued in its LADO_HOME unless it took telemetry_on, which sends to a local port."""
    from lado import telemetry

    # off_by, not state(): state() makes LADO_HOME, which some tests check is not there.
    off_by = telemetry.off_by(os.environ)
    if off_by != "LADO_TELEMETRY=0":
        pytest.fail(
            f"statistics are not off by LADO_TELEMETRY=0 (off by: {off_by}): "
            "tests/conftest.py must set it for the whole test run",
            pytrace=False,
        )
    yield
    if "telemetry_on" in request.fixturenames:
        return
    sent, outbox = lado_home / "telemetry" / "sent.json", lado_home / "telemetry" / "outbox"
    left = ([sent] if sent.exists() else []) + (sorted(outbox.iterdir()) if outbox.is_dir() else [])
    if left:
        pytest.fail(
            f"the test sent or queued statistics without telemetry_on: {left[0]}",
            pytrace=False,
        )


@pytest.fixture
def published(tmp_path, monkeypatch):
    """The update check switched on, reading a local index: published(**releases) writes it
    (agent_helpers.pypi_index)."""
    path = tmp_path / "pypi-index.json"
    monkeypatch.delenv("LADO_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(path))
    return lambda **releases: write_index(path, **releases)


@pytest.fixture
def telemetry_on(monkeypatch, lado_home):
    """Sending switched on: the human said yes, nothing in the environment switches it off,
    and the endpoint is a local port nothing listens on (telemetry_endpoint gives one that
    answers)."""
    from lado import telemetry

    monkeypatch.delenv("LADO_TELEMETRY", raising=False)
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    monkeypatch.setenv("LADO_TELEMETRY_URL", f"http://127.0.0.1:{_closed_port()}/batch/")
    telemetry.choose("on")


def _closed_port() -> int:
    """A local port nothing listens on (as long as nothing takes it in between)."""
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def telemetry_endpoint(telemetry_on, monkeypatch):
    """A local statistics endpoint: `requests` keeps each request's JSON body, `status` is
    what it answers (200)."""
    import http.server
    import threading

    class Endpoint:
        requests: list = []
        status = 200

    endpoint = Endpoint()
    endpoint.requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            endpoint.requests.append(json.loads(body))
            self.send_response(endpoint.status)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    endpoint.url = f"http://127.0.0.1:{server.server_address[1]}/batch/"
    monkeypatch.setenv("LADO_TELEMETRY_URL", endpoint.url)
    yield endpoint
    server.shutdown()
    server.server_close()


@pytest.fixture
def repo(tmp_path):
    return init_repo(tmp_path / "My Repo")


@pytest.fixture
def git_config(tmp_path_factory, monkeypatch):
    """git's global config for every git the test runs, never the user's: a file of its own
    (GIT_CONFIG_GLOBAL, no system config; outside tmp_path, which tests list) that names an
    author; the file's path. Empty it (`write_text("")`) for a git that does not know the
    author."""
    path = tmp_path_factory.mktemp("git-config") / "gitconfig"
    path.write_text("[user]\n\tname = LADO test\n\temail = test@lado.invalid\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(path))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return path


@pytest.fixture
def loop_starts(monkeypatch):
    """Record the sessions whose loop is started, instead of starting a process."""
    from lado import loop

    started = []
    monkeypatch.setattr(loop, "start", started.append)
    return started


@pytest.fixture(autouse=True)
def claude_config(tmp_path, tmp_path_factory, monkeypatch):
    """Claude Code's global config for the agents (CLAUDE_CONFIG_DIR), never the user's, in
    every test, since LADO writes its trust there (outside tmp_path, which tests list): it
    trusts the folder of the `repo` fixture, as Claude Code would after the human said yes
    there. trust(*folders) replaces what it trusts (none: LADO records the trust of the
    folder an agent starts in, note(repo) its line); refuse(): it trusts none and LADO cannot
    record the trust in `repo`'s folder, whose entry is no JSON object, so a Claude agent
    waits there with reason(repo)."""
    folder = tmp_path_factory.mktemp("claude-config")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(folder))
    repo = tmp_path / "My Repo"

    class Config:
        path = folder / ".claude.json"

        def trust(self, *folders):
            projects = {str(f): {"hasTrustDialogAccepted": True} for f in folders}
            self.path.write_text(json.dumps({"projects": projects}))

        def refuse(self):
            self.path.write_text(json.dumps({"projects": {str(repo): None}}))

        def note(self, repo):
            return f"LADO recorded Claude Code's trust in {repo} in {self.path}"

        def reason(self, repo):
            return (
                f"Claude Code asks whether to trust {repo}: LADO could not record the trust "
                f"({self.path}: the entry of {repo} in its projects is not a JSON object); in "
                'its terminal choose "Yes, I trust this folder" (Enter alone answers "No, '
                'exit" and closes the agent)'
            )

    config = Config()
    config.trust(tmp_path / "My Repo")
    return config


@pytest.fixture(autouse=True)
def codex_home(tmp_path, monkeypatch):
    """The user's Codex home (CODEX_HOME), never the user's ~/.codex; not made. A Codex agent
    reads its config.toml (lado.providers.codex)."""
    folder = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(folder))
    return folder


class CliLogins:
    """What the agent CLIs' login status commands answer in a test (base.run_status): by
    default nothing runs and each is unknown, so no login holds an agent and no first-run
    key is written; `answer(command, code, stdout, stderr="")` or `answer(command,
    problem)` sets one, `logged_in()` logs Claude Code in with a token. `calls` keeps the
    (argv, env) asked."""

    UNREAD = "LADO's tests run no agent CLI's status command"

    def __init__(self):
        self.answers: dict[str, object] = {}
        self.calls: list[tuple[list[str], dict]] = []

    def answer(self, command, code_or_problem, stdout="", stderr=""):
        if isinstance(code_or_problem, str):
            self.answers[command] = code_or_problem
        else:
            self.answers[command] = (code_or_problem, stdout, stderr)

    def logged_in(self, method="oauth_token"):
        data = {"loggedIn": True, "authMethod": method, "configDirectory": "/c"}
        if method == "api_key":
            data["apiKeySource"] = "ANTHROPIC_API_KEY"
        self.answer("claude", 0, json.dumps(data))

    def logged_out(self):
        self.answer("claude", 1, json.dumps({"loggedIn": False, "authMethod": "none"}))

    def run(self, argv, env):
        self.calls.append((list(argv), dict(env)))
        answer = self.answers.get(os.path.basename(argv[0]), self.UNREAD)
        if isinstance(answer, str):
            return answer
        code, out, err = answer
        return subprocess.CompletedProcess(argv, code, out, err)


@pytest.fixture(autouse=True)
def cli_logins(monkeypatch):
    """The agent CLIs' login status in every unit test (CliLogins), never the user's."""
    from lado.providers import base

    logins = CliLogins()
    monkeypatch.setattr(base, "run_status", logins.run)
    return logins


@pytest.fixture
def fake_clis(tmp_path, monkeypatch, claude_config):
    """Stand-ins for the agent CLIs on PATH, which a launch looks its CLI up on; the folder."""
    folder = tmp_path / "fake-clis"
    folder.mkdir()
    for name in ("claude", "codex", "kilo", "opencode", "noskills"):
        (folder / name).write_text("#!/bin/sh\n")
        (folder / name).chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    return folder


@pytest.fixture
def fake_tmux(monkeypatch, loop_starts, fake_clis):
    """Record tmux calls instead of running them; no session loop is started either."""
    from lado import gui_session, logins, terminal, tmux

    calls = []
    # The hook it is given (runtime passes gui_session.ensure_server) is not called.
    monkeypatch.setattr(
        tmux, "new_session", lambda *a, **k: calls.append(("new_session", *a)) or []
    )
    monkeypatch.setattr(gui_session, "server_place", lambda socket: None)  # no tmux server
    monkeypatch.setattr(tmux, "new_window", lambda *a: calls.append(("new_window", *a)))
    monkeypatch.setattr(tmux, "send_text", lambda *a: calls.append(("send_text", *a)))

    def has_session(session):
        alive = False
        for call in calls:
            if call[0] in ("new_session", "kill_session") and call[1] == session:
                alive = call[0] == "new_session"
        return alive

    def list_windows(session):
        windows = []
        for call in calls:
            if call[0] == "new_session" and call[1] == session:
                windows = [call[2]]
            elif call[0] == "new_window" and call[1] == session:
                windows.append(call[2])
            elif call[0] == "kill_window" and call[1] == session:
                windows = [w for w in windows if w != call[2]]
            elif call[0] == "kill_session" and call[1] == session:
                windows = []
        if not has_session(session):
            raise tmux.TmuxError(f"can't find session: {session}")
        return windows

    monkeypatch.setattr(tmux, "has_session", has_session)
    monkeypatch.setattr(tmux, "list_windows", list_windows)
    monkeypatch.setattr(tmux, "kill_session", lambda s: calls.append(("kill_session", s)))
    monkeypatch.setattr(tmux, "kill_window", lambda *a: calls.append(("kill_window", *a)))
    monkeypatch.setattr(tmux, "popup", lambda *a: calls.append(("popup", *a)))
    monkeypatch.setattr(terminal, "close_viewers", lambda s: calls.append(("close_viewers", s)))
    monkeypatch.setattr(logins, "end_windows", lambda: calls.append(("end_login_windows",)) or [])
    return calls
