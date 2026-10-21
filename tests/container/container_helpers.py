"""What the container tests share: the `docker` CLI, the image under test, a free port, the
server's health on the host's loopback, and a container of the image."""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parents[2]
IMAGE = os.environ.get("LADO_TEST_IMAGE", "lado:local")
PYTHON = "/opt/uv/tools/lado/bin/python"  # LADO's own Python in the image
# Every container a test makes: no statistics, no look at PyPI.
QUIET = ["-e", "LADO_TELEMETRY=0", "-e", "LADO_NO_UPDATE_CHECK=1"]
# Each container, volume and compose project of this test run is named PREFIX<hex>: the
# run's own prefix, so a run beside it (another worktree) is not taken for one left behind.
PREFIX = f"lado-test-{secrets.token_hex(3)}-"


def new_name() -> str:
    return f"{PREFIX}{secrets.token_hex(4)}"


def docker(*args: str, check: bool = True, timeout: float = 120, **kw):
    """`docker <args>`; with `check`, a failure raises with docker's own words (stderr),
    which a CalledProcessError's message leaves out."""
    done = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, **kw)
    if check and done.returncode != 0:
        raise AssertionError(
            f"docker {' '.join(args)}: exit {done.returncode}\n{done.stderr}{done.stdout}"
        )
    return done


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def health(port: int, timeout: float = 90) -> dict:
    """/api/health on the host's loopback, once the server answers."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=5) as r:
                return json.loads(r.read())
        except OSError as e:
            if time.monotonic() > deadline:
                raise AssertionError(f"no /api/health on 127.0.0.1:{port} in {timeout} s") from e
            time.sleep(0.5)


def run_container(
    name: str, *args: str, home: str | None = None, command: tuple[str, ...] = ()
) -> None:
    """The image as one `docker run` starts it, with the home volume `home`, by default one
    of its own (`<name>-home`), and `command` in place of the image's when given."""
    home = home or f"{name}-home"
    docker(
        "run", "-d", "--name", name, *QUIET, "-v", f"{home}:/home/lado", *args, IMAGE, *command
    )  # fmt: skip


def seed_home(volume: str, lado_db: bytes) -> None:
    """A new home volume `volume` whose ~/.lado/lado.db is `lado_db` (made on the host), as
    an older image left it: the image's home in it as a first mount copies it, then the
    file, all of it lado's (uid 1000)."""
    subprocess.run(
        [
            "docker", "run", "--rm", "-i", "-u", "0", "--entrypoint", "sh",
            "-v", f"{volume}:/home/lado", IMAGE, "-c",
            "mkdir -p /home/lado/.lado && cat > /home/lado/.lado/lado.db "
            "&& chown -R 1000:1000 /home/lado/.lado",
        ],
        input=lado_db, capture_output=True, check=True, timeout=120,
    )  # fmt: skip


def schema(volume: str) -> int:
    """The schema of lado.db in the home volume `volume`, read by a container of its own
    that runs no LADO command, so nothing migrates it. As root, since the entrypoint may
    have given the home to the workspace's owner (uid 1001 on GitHub's runner), and
    immutable, so it writes nothing there (no -shm or -wal of root's): no LADO may run on
    the volume meanwhile."""
    done = docker(
        "run", "--rm", "-u", "0", "--entrypoint", PYTHON, "-v", f"{volume}:/home/lado", IMAGE,
        "-c",
        "import sqlite3; db = sqlite3.connect("
        "'file:/home/lado/.lado/lado.db?immutable=1', uri=True); "
        "print(db.execute('PRAGMA user_version').fetchone()[0])",
        check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr
    return int(done.stdout.strip())


def sessions(volume: str) -> dict[str, tuple[bool, bool]]:
    """Each session of lado.db in the home volume `volume`: whether it is stopped and whether
    it is marked to resume at the container's start. Read as schema() reads, with no LADO
    running on the volume."""
    done = docker(
        "run", "--rm", "-u", "0", "--entrypoint", PYTHON, "-v", f"{volume}:/home/lado", IMAGE,
        "-c",
        "import json, sqlite3; db = sqlite3.connect("
        "'file:/home/lado/.lado/lado.db?immutable=1', uri=True); "
        "print(json.dumps({n: [s is not None, bool(m)] for n, s, m in db.execute("
        "'SELECT name, stopped_at, resume_at_start FROM sessions')}))",
        check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr
    return {name: tuple(row) for name, row in json.loads(done.stdout).items()}


def on_volume(volume: str, script: str) -> None:
    """`script` in sh as lado (uid 1000) with the home volume `volume` at /home/lado, no
    LADO running on it."""
    docker(
        "run", "--rm", "-u", "1000", "--entrypoint", "sh", "-v", f"{volume}:/home/lado",
        IMAGE, "-c", script,
    )  # fmt: skip


def remove_container(name: str, home: str | None = None) -> None:
    docker("rm", "-f", name, check=False)
    docker("volume", "rm", home or f"{name}-home", check=False)


class Container:
    """A running container of the image, its UI server on the host's `port`."""

    def __init__(self, name: str, port: int):
        self.name, self.port = name, port

    def exec(self, *cmd: str, check: bool = True, input: str | None = None, timeout=120):
        return docker("exec", "-i", self.name, *cmd, check=check, input=input, timeout=timeout)

    def sh(self, script: str, **kw):
        return self.exec("sh", "-c", script, **kw)

    def python(self, code: str) -> str:
        return self.exec(PYTHON, "-c", code).stdout.strip()

    def write(self, path: str, text: str):
        self.sh(f'mkdir -p "$(dirname {path})" && cat > {path}', input=text)

    def logs(self) -> str:
        done = docker("logs", self.name, check=False)
        return done.stdout + done.stderr

    def agent_status(self, session: str, agent: str) -> str:
        return self.python(
            f"from lado import state; a = state.get_agent({session!r}, {agent!r}); "
            "print(a.status if a else 'gone')"
        )


ENDPOINT_PORT = 8399  # the fake model API, on the container's own loopback
KEY = "container-fake-key-0123456789abcdef"  # no account's key: the endpoint takes none


def fake_endpoint(container: Container) -> None:
    """The fake model API on the container's own loopback, started (again: a container's
    start runs only its command) and answering."""
    endpoint = str(ROOT / "tests" / "fake_endpoint.py")
    docker("cp", endpoint, f"{container.name}:/tmp/fake_endpoint.py")
    docker(
        "exec", "-d", container.name, PYTHON, "-I", "/tmp/fake_endpoint.py",
        str(ENDPOINT_PORT), "/tmp/endpoint.jsonl",
    )  # fmt: skip
    deadline = time.monotonic() + 30
    probe = f"import socket; socket.create_connection(('127.0.0.1', {ENDPOINT_PORT}), 1)"
    while container.exec(PYTHON, "-c", probe, check=False).returncode != 0:
        if time.monotonic() > deadline:
            raise AssertionError("the fake model API did not answer in the container")
        time.sleep(0.2)


def git_repo(container: Container, path: str) -> None:
    """A repository with one commit at `path` in the container, lado's."""
    container.sh(
        f"git init -q -b main {path} && git -C {path} -c user.name=lado "
        "-c user.email=lado@example.com commit -q --allow-empty -m first"
    )


def claude_session(
    container: Container,
    repo: str,
    session: str = "smoke",
    *more: str,
    start_args: tuple[str, ...] = (),
) -> None:
    """A Claude Code session of LADO on `repo` in `container`, against the fake model API on
    the container's own loopback; returns once its supervisor is idle. Claude Code trusts
    the `more` repositories too, for the sessions start_claude starts there after;
    `start_args` go to `lado start` (e.g. `--kit`)."""
    fake_endpoint(container)
    # Claude Code pointed at it through the login shell, as a human gives a token; its
    # first-run screens, the bypass mode's disclaimer and the repository's trust done.
    container.sh(
        "cat >> ~/.profile <<'EOF'\n"
        f"export ANTHROPIC_BASE_URL=http://127.0.0.1:{ENDPOINT_PORT}\n"
        f"export ANTHROPIC_AUTH_TOKEN={KEY}\n"
        "export CLAUDE_CODE_MAX_RETRIES=0\n"
        "export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1\n"
        "EOF"
    )
    container.write(
        "/home/lado/.claude/.claude.json",
        json.dumps(
            {
                "hasCompletedOnboarding": True,
                "bypassPermissionsModeAccepted": True,
                "projects": {r: {"hasTrustDialogAccepted": True} for r in (repo, *more)},
            }
        ),
    )
    start_claude(container, repo, session, *start_args)


def start_claude(container: Container, repo: str, session: str, *args: str) -> None:
    """Another Claude Code session in a container claude_session set up, `args` given to
    `lado start`; returns once its supervisor is idle."""
    started = container.exec(
        "lado", "start", repo, "--name", session, "--provider", "claude",
        "--permission-mode", "bypassPermissions", "--no-attach", *args, check=False,
    )  # fmt: skip
    assert started.returncode == 0, started.stdout + started.stderr
    wait_status(container, session, "supervisor", "idle")


def wait_status(container: Container, session: str, agent: str, want: str, timeout=120) -> None:
    status, deadline = "", time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = container.agent_status(session, agent)
        if status == want:
            return
        time.sleep(0.5)
    raise AssertionError(f"{agent} is {status}, not {want}")


def agent_pid(container: Container, session: str, window: str) -> int:
    """The agent CLI's own process: the window's pane process, as lado.agent_env execs the
    CLI in place and Claude Code 2.x is a native binary. Checked, never guessed: its
    executable must be the file the `claude` command names."""
    pane = container.exec(
        "tmux", "-L", "lado", "display-message", "-p", "-t", f"{session}:{window}", "#{pane_pid}"
    ).stdout.strip()
    running = container.exec("readlink", f"/proc/{pane}/exe").stdout.strip()
    claude = container.sh('readlink -f "$(command -v claude)"').stdout.strip()
    assert running == claude, f"pane process {pane} runs {running}, not claude ({claude})"
    return int(pane)


def agent_environ(container: Container, session: str, window: str) -> list[str]:
    pid = agent_pid(container, session, window)
    return container.exec("cat", f"/proc/{pid}/environ").stdout.split("\0")
