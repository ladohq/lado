"""The canary of a project's secrets (openspec change project-secrets, "A project's secrets
stay out of LADO's records"): a unique value set as a project's secret through the CLI and
through a real server, given to every kind of agent, is found nowhere else: not in any
process's arguments, the tmux server's environment, any file under LADO_HOME but its own,
any output of the CLI, any answer of the API (refusals included), the change feed, or
telemetry's payload. No browser: the UI's feed is the server's change feed; the browser's
side is tests/ui/test_projects_section.py.

The Projects section's API (openspec change projects-section) is read too: the list, New
project's id and create, and the project with the names the outside folder gives too and the
secret files its agents do not get. The session in the project starts through the server, as
New session's Project way starts it (openspec change new-session-in-project). An outside
value of the same name and a hand-made secret file of a loose mode are canaries of their
own. Each kind of agent's start is followed by a look at every process's arguments; every
tmux session's environment is read, and no secret's name is in a bug report. The project is
deleted through the API at the end (openspec change project-delete): its preview and its
answers hold no value, and no file under LADO_HOME holds one after it."""

import json
import os
import stat
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import fake_provider
import pytest
from agent_helpers import install_kit, wait_for
from test_project_sessions import _approve_and_start, stop_all
from test_project_variables import TINY, environ, tell, wait_idle

from lado import project_secrets, projects, runs, state, tmux
from lado.server import auth
from lado.server import run as server_run

pytestmark = pytest.mark.integration

CLI_NAME, API_NAME, LOOSE_NAME = "IT_CANARY_TOKEN", "IT_CANARY_API_KEY", "IT_CANARY_LOOSE"


def lado(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        fake_provider.lado_command(*args),
        input=stdin,
        stdin=None if stdin is not None else subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
    )


class Api:
    """A real server's API, with the token's cookie and its own origin."""

    def __init__(self, info: dict):
        self.url = info["url"]
        self.headers = {
            "Cookie": f"{auth.cookie_name(info['port'])}={auth.token()}",
            "Origin": info["url"],
            "Content-Type": "application/json",
        }

    def call(self, method: str, path: str, body: object = None) -> tuple[int, str]:
        data = None if body is None else json.dumps(body).encode()
        ask = urllib.request.Request(
            self.url + path, data=data, method=method, headers=self.headers
        )
        try:
            with urllib.request.urlopen(ask, timeout=30) as answer:
                return answer.status, answer.read().decode()
        except urllib.error.HTTPError as refused:
            return refused.code, refused.read().decode()

    def feed(self, seconds: float) -> str:
        """What the change feed sends from its start for `seconds`."""
        ask = urllib.request.Request(f"{self.url}/api/events?after=0", headers=self.headers)
        got: list[bytes] = []
        stream = urllib.request.urlopen(ask, timeout=30)

        def read() -> None:
            try:
                while line := stream.readline():
                    got.append(line)
            except (OSError, ValueError, AttributeError):
                pass  # closed below, maybe mid-read

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        time.sleep(seconds)
        stream.close()
        reader.join(5)
        return b"".join(got).decode()


def files_holding(root: Path, value: bytes, skip: list[Path]) -> list[Path]:
    """Every file under `root` holding `value`, but under `skip`; a link to a file is read
    through (a link to a folder is not followed: no loop). A read that fails fails the
    canary, but for a socket or a pipe, which hold no file's content, and a file gone
    meanwhile."""
    found = []
    for folder, _, names in os.walk(root):
        for name in names:
            path = Path(folder) / name
            if any(path.is_relative_to(s) for s in skip):
                continue
            try:
                kind = os.stat(path).st_mode
                if stat.S_ISSOCK(kind) or stat.S_ISFIFO(kind):
                    continue
                if value in path.read_bytes():
                    found.append(path)
            except FileNotFoundError:
                pass  # gone meanwhile, or a link to nothing
    return found


def no_canary_in_processes(*canaries: str) -> None:
    """No process's arguments hold a canary: looked at after each kind of agent starts."""
    processes = subprocess.run(["ps", "-ww", "-eo", "args"], capture_output=True, text=True)
    assert processes.returncode == 0 and "lado" in processes.stdout
    assert [c for c in canaries if c in processes.stdout] == []


def tmux_environments() -> str:
    """The global environment of LADO's tmux server and each of its sessions'."""
    socket = ["tmux", "-L", tmux.socket()]
    listed = subprocess.run(
        [*socket, "list-sessions", "-F", "#{session_name}"], capture_output=True, text=True
    )
    assert listed.returncode == 0 and listed.stdout.split(), listed.stderr
    texts = []
    for target in (["-g"], *(["-t", name] for name in listed.stdout.split())):
        shown = subprocess.run(
            [*socket, "show-environment", *target], capture_output=True, text=True
        )
        assert shown.returncode == 0 and shown.stdout, (target, shown.stderr)
        texts.append(shown.stdout)
    return "\n".join(texts)


@pytest.fixture
def shop(tmp_path, monkeypatch, git_config, telemetry_endpoint):
    """The project shop with its repository frontend, the plain variable BOARD_URL, the
    flow kit itcanary; statistics on, sent to a local endpoint."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    monkeypatch.delenv("LADO_ENV_DIR", raising=False)
    projects.create("shop", None)
    projects.add_new("shop", "frontend")
    projects.set_variable("shop", "BOARD_URL", "https://board")
    kit = tmp_path / "kits" / "itcanary"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: itcanary\nversion: 1.0.0\n")
    (kit / "flows" / "tiny.yaml").write_text(TINY)
    install_kit(kit)
    yield telemetry_endpoint
    stop_all()
    if server_run.running():
        server_run.stop()


def test_files_holding_reads_links_and_fails_on_a_read_error(tmp_path):
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "file").write_bytes(b"canary-x")
    root = tmp_path / "root"
    root.mkdir()
    (root / "link").symlink_to(tmp_path / "out" / "file")
    (root / "folder-link").symlink_to(tmp_path / "out")
    (root / "gone").symlink_to(tmp_path / "nothing")
    assert files_holding(root, b"canary-x", []) == [root / "link"]
    (root / "closed").write_bytes(b"x")
    (root / "closed").chmod(0)
    if os.geteuid() != 0:  # root reads it all the same
        with pytest.raises(PermissionError):
            files_holding(root, b"canary-x", [])


def test_a_project_secret_is_found_nowhere_else(shop, tmp_path, monkeypatch, fakes_known_to_lado):
    canary = f"canary-{uuid.uuid4().hex}"
    outside, loose = f"outside-{uuid.uuid4().hex}", f"loose-{uuid.uuid4().hex}"
    lados = f"lado-secret-{uuid.uuid4().hex}"  # LADO's secret (openspec provider-logins)
    canaries = (canary, outside, loose, lados)
    said: list[str] = []  # every output and answer
    # The outside folder gives CLI_NAME too: the project's value goes over it.
    given = tmp_path / "outside"
    given.mkdir()
    (given / CLI_NAME).write_text(outside)
    monkeypatch.setenv("LADO_ENV_DIR", str(given))

    # The CLI: set from stdin; refused with the value as an argument and on a plain name.
    done = lado("project", "set", "shop", CLI_NAME, "--secret", stdin=f"{canary}\n")
    assert done.returncode == 0, done.stderr
    said += [done.stdout, done.stderr]
    for refused in (
        lado("project", "set", "shop", CLI_NAME, canary, "--secret"),
        lado("project", "set", "shop", "BOARD_URL", "--secret", stdin=canary),
        lado("project", "set", "shop", "PATH", "--secret", stdin=canary),
    ):
        assert refused.returncode == 1
        said += [refused.stdout, refused.stderr]

    # The API of a real server: set, replaced, and refused (400, 404, 422).
    api = Api(server_run.wait_ready(server_run.start_background(None, 0)))
    for value in (f"{canary}-old", f"{canary}-api"):
        status, body = api.call("PUT", f"/api/projects/shop/secrets/{API_NAME}", {"value": value})
        assert status == 200, body
        said.append(body)
    for method, path, body, expected in [
        ("PUT", "/api/projects/shop/secrets/PATH", {"value": canary}, 400),
        ("PUT", "/api/projects/shop/secrets/BOARD_URL", {"value": canary}, 400),
        ("PUT", "/api/projects/acme/secrets/X", {"value": canary}, 404),
        ("PUT", f"/api/projects/shop/secrets/{API_NAME}", {"secret": canary}, 422),
        ("PUT", f"/api/projects/shop/secrets/{API_NAME}", {"value": [canary]}, 422),
        ("PUT", "/api/projects/shop/variables/BOARD_URL", {"value": 5}, 422),
    ]:
        status, answer = api.call(method, path, body)
        assert status == expected, answer
        said.append(answer)
    assert project_secrets.names("shop") == [API_NAME, CLI_NAME]
    # A secret file made by hand and left readable by others: its agents do not get it.
    (project_secrets.folder("shop") / LOOSE_NAME).write_text(loose)
    (project_secrets.folder("shop") / LOOSE_NAME).chmod(0o644)

    # The Projects section's API: the list, New project's id and create, and the project
    # with the names the outside folder gives too and the files its agents do not get.
    for method, path, body, expected in [
        ("GET", "/api/projects", None, 200),
        ("GET", "/api/project-id?title=Shop", None, 200),
        ("GET", "/api/project-id?id=acme", None, 200),
        ("POST", "/api/projects", {"id": "acme", "title": "ACME"}, 200),
        ("POST", "/api/projects", {"id": "shop"}, 400),
    ]:
        status, answer = api.call(method, path, body)
        assert status == expected, answer
        said.append(answer)
    status, body = api.call("GET", "/api/projects/shop")
    assert status == 200, body
    page = json.loads(body)
    assert page["overrides"] == [CLI_NAME]
    # A login variable kept as LADO's secret in Settings → Providers and environment: every
    # agent gets it (the project does not set it), no answer gives it back.
    token = f"/api/providers/fake-login/variables/{fake_provider.TOKEN}"
    for method, path, sent, expected in [
        ("PUT", token, {"value": f"{lados}-old"}, 200),
        ("PUT", token, {"value": lados}, 200),
        ("PUT", "/api/providers/fake-login/variables/GH_TOKEN", {"value": lados}, 400),
        ("PUT", token, {"secret": lados}, 422),
        ("PUT", token, {"value": [lados]}, 422),
        ("GET", "/api/providers/logins", None, 200),
    ]:
        status, answer = api.call(method, path, sent)
        assert status == expected, answer
        said.append(answer)
    assert project_secrets.lado_names() == [fake_provider.TOKEN]
    assert page["unused"] == [
        {"name": LOOSE_NAME, "reason": "readable or writable by others: chmod 600 it"}
    ]
    said.append(body)

    # Every kind of agent of a session in the project gets the secrets; the session starts
    # through the server, as New session's Project way starts it (what it shows first).
    status, body = api.call("GET", "/api/project-launch?project=shop")
    assert status == 200 and json.loads(body)["repo"] == "frontend", body
    said.append(body)
    status, body = api.call(
        "POST",
        "/api/sessions",
        {
            "where": {"kind": "project", "project": "shop", "repo": "frontend"},
            "kits": ["default", "itcanary"],
            "provider": "fake",
        },
    )
    assert status == 200, body
    assert json.loads(body)["session"]["project"] == "shop"
    said.append(body)
    assert environ("shop-frontend", "supervisor")[CLI_NAME] == canary
    assert environ("shop-frontend", "supervisor")[fake_provider.TOKEN] == lados
    assert LOOSE_NAME not in environ("shop-frontend", "supervisor")
    no_canary_in_processes(*canaries)
    wait_idle("shop-frontend")
    tell("shop-frontend", "supervisor", "spawn sleep 0")
    assert environ("shop-frontend", "worker")[API_NAME] == f"{canary}-api"
    no_canary_in_processes(*canaries)
    run = runs.start("shop-frontend", "tiny", "build it", notices=[])
    wait_idle("shop-frontend")
    tell("shop-frontend", "supervisor", f"spawnrun {run.name}")
    runner = wait_for(
        lambda: next((a for a in state.list_agents("shop-frontend") if a.run), None),
        "the run's worker",
        "shop-frontend",
    )
    assert environ("shop-frontend", runner.name)[CLI_NAME] == canary
    no_canary_in_processes(*canaries)
    (projects.folder("shop") / "frontend" / "brief.md").write_text("# Fix the login\n")
    _approve_and_start("shop-frontend", "fix-login")
    assert environ("fix-login", "supervisor")[CLI_NAME] == canary
    no_canary_in_processes(*canaries)

    # While the agents run: not the tmux server's environment, nor any session's.
    environments = tmux_environments()
    assert [c for c in canaries if c in environments] == []
    home = state.home_path()
    # The launch files were read and removed by the windows that run.
    assert sorted(home.rglob("env.json")) == []
    secrets_folder = project_secrets.folder("shop")
    # fake-agents/ is the fake agent's own report of its environment, as a real CLI's
    # memory: not LADO's record.
    skip = [secrets_folder, project_secrets.lado_folder(), home / "fake-agents"]
    for value in canaries:
        assert files_holding(home, value.encode(), skip) == []

    # A bug report names no secret: neither the CLI's nor the UI's.
    report = lado("bug-report")
    assert report.returncode == 0, report.stderr
    status, ui_report = api.call("GET", "/api/bug-report")
    assert status == 200, ui_report
    for text in (report.stdout, report.stderr, ui_report):
        assert [name for name in (CLI_NAME, API_NAME, LOOSE_NAME) if name in text] == []
    said += [report.stdout, report.stderr, ui_report]

    # What the human runs and reads.
    for args in (
        ("project", "show", "shop"),
        ("doctor",),
        ("log", "shop-frontend"),
        ("log", "fix-login"),
        ("ls",),
    ):
        done = lado(*args)
        said += [done.stdout, done.stderr]
    status, body = api.call("GET", "/api/projects/shop")
    assert status == 200 and API_NAME in body
    said.append(body)
    feed = api.feed(2.0)
    assert '"kind"' in feed  # the feed was read: its replay of the changes so far
    said.append(feed)

    # Telemetry's payload: what it queued, and what it sent.
    done = lado("telemetry", "send")
    said += [done.stdout, done.stderr]
    wait_for(lambda: shop.requests, "a post of the statistics", "shop-frontend")
    said += [json.dumps(body) for body in shop.requests]

    # The delete through the API (openspec change project-delete): refused while its
    # sessions run, then previewed by names only and done; the secrets' folder goes with it.
    status, body = api.call("DELETE", "/api/projects/shop")
    assert status == 400 and "has sessions not stopped" in body, body
    said.append(body)
    assert sorted(path.name for path in secrets_folder.iterdir()) == sorted(
        [API_NAME, CLI_NAME, LOOSE_NAME]
    )
    stop_all()
    status, body = api.call("GET", "/api/projects/shop/deletion")
    assert status == 200, body
    preview = json.loads(body)
    assert API_NAME in preview["secrets"] and CLI_NAME in preview["secrets"]
    assert {"fix-login", "shop-frontend"} <= {one["name"] for one in preview["sessions"]}
    said.append(body)
    status, body = api.call("DELETE", "/api/projects/shop")
    assert status == 204, body
    said.append(body)
    assert not os.path.lexists(project_secrets.data_folder("shop"))
    assert state.get_project("shop") is None
    for args in (("log", "shop-frontend"), ("project", "list"), ("ls",)):
        done = lado(*args)
        said += [done.stdout, done.stderr]
    feed = api.feed(2.0)
    assert '"kind"' in feed
    said.append(feed)

    server_run.stop()
    assert [text for text in said if any(c in text for c in canaries)] == []
    # The project's secrets' folder is gone: of LADO_HOME only LADO's secrets are skipped.
    for value in canaries:
        kept = [project_secrets.lado_folder(), home / "fake-agents"]
        assert files_holding(home, value.encode(), kept) == []
