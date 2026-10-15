"""Container tests: LADO's image (docker/Dockerfile) with real Docker and no model. They drive
the `docker` CLI from the host against an image built already (`make docker`;
`LADO_TEST_IMAGE`, else lado:local) and skip when Docker does not run or the image is
missing; CI's cell (scripts/smoke_ci.py container) makes a skip red.

Each test's containers, volumes and compose projects are named with this run's prefix
(container_helpers.PREFIX) and removed after it, also when it fails; the session's teardown
fails when one is left. A test that fails in its setup or its call keeps each container it
started (`docker logs` and LADO's logs) in real_clis.EVIDENCE, as a failed smoke test does:
a container is registered on the test before anything can fail and removed by a finalizer,
which runs after the failure's report.
"""

import os
import re
import shutil
import time

import agent_helpers
import pytest
import real_clis
from container_helpers import (
    IMAGE,
    PREFIX,
    ROOT,
    Container,
    docker,
    free_port,
    health,
    new_name,
    remove_container,
    run_container,
    seed_home,
)

from lado import state


@pytest.fixture(scope="session", autouse=True)
def image() -> str:
    if shutil.which("docker") is None or docker("info", check=False).returncode != 0:
        pytest.skip("docker does not run")
    if docker("image", "inspect", IMAGE, check=False).returncode != 0:
        pytest.skip(f"no image {IMAGE}: run make docker")
    yield IMAGE
    left = {
        kind: docker(*ls, "-q", "--filter", f"name={PREFIX}").stdout.split()
        for kind, ls in (("containers", ["ps", "-a"]), ("volumes", ["volume", "ls"]))
    }
    assert left == {"containers": [], "volumes": []}, f"left behind: {left}"


def keep(item, started: Container) -> None:
    """Keep `started`'s logs when `item` fails (pytest_runtest_makereport)."""
    item.__dict__.setdefault("lado_containers", []).append(started)


@pytest.fixture
def start(request, projects_volume):
    """Start the image as one `docker run` does: `start(port, *args, home=None)`, the server
    on the host's `port` by `args`, its home volume `home` (by default one of its own, a
    name of this run's prefix for another container of the test to take); the container
    and the volume removed after the test. It takes `projects_volume` so that fixture's
    teardown, which removes the volumes a container mounts, runs after this one's."""

    def start(port: int, *args: str, home: str | None = None, command=()) -> Container:
        started = Container(new_name(), port)
        keep(request.node, started)
        request.addfinalizer(lambda: remove_container(started.name, home))
        run_container(started.name, *args, home=home, command=command)
        return started

    return start


@pytest.fixture
def projects_volume(request):
    """`projects_volume(uid, gid, mode="755")`: a named volume whose root belongs to
    `uid:gid` with `mode`, as a Linux host's projects folder of that user looks in the
    container; removed after the test. Its path in a container is the test's choice."""

    def make(uid: int, gid: int, mode: str = "755") -> str:
        name = f"{new_name()}-proj"
        request.addfinalizer(lambda: docker("volume", "rm", "-f", name, check=False))
        docker(
            "run", "--rm", "-u", "0", "--entrypoint", "sh", "-v", f"{name}:/p", IMAGE,
            "-c", f"chown {uid}:{gid} /p && chmod {mode} /p",
        )  # fmt: skip
        return name

    return make


@pytest.fixture
def old_home(request, tmp_path, monkeypatch):
    """`old_home(volume=None, broken=False)`: a home volume (by default a new name of this
    run's prefix) whose lado.db has the schema before this LADO's and a stopped session
    "old", made on the host by this checkout's own lado.state, as the image's LADO is; with
    `broken` the schema's number is set back but the last step's change is there, so the
    migration fails. Its schema before, and the volume, removed after the test."""

    def make(volume: str | None = None, broken: bool = False) -> tuple[str, int]:
        volume = volume or f"{new_name()}-home"
        request.addfinalizer(lambda: docker("volume", "rm", "-f", volume, check=False))
        monkeypatch.setenv("LADO_HOME", str(tmp_path / f"host-{volume}"))
        state.add_session(state.Session("old", "/home/lado/repo", None, "claude"))
        state.stop_session("old")
        before = state.SCHEMA_VERSION - 1
        if broken:
            with state.connect() as db:
                db.execute(f"PRAGMA user_version = {before}")
        else:
            agent_helpers.previous_schema()
        seed_home(volume, agent_helpers.database())
        monkeypatch.delenv("LADO_HOME")
        return volume, before

    return make


@pytest.fixture
def container(start):
    """The image on a free port other than 8765, its server answering."""
    port = free_port()
    started = start(port, "-e", f"LADO_PORT={port}", "-p", f"127.0.0.1:{port}:{port}")
    health(port)
    return started


# A compose project's own settings for a test: no statistics, no look at PyPI.
QUIET_OVERRIDE = """services:
  lado:
    environment:
      LADO_TELEMETRY: "0"
      LADO_NO_UPDATE_CHECK: "1"
"""


class Compose:
    """A compose project of docker/compose.yaml; `run(*args)` is its `docker compose`."""

    def __init__(self, project: str, port: int, override, env: dict):
        self.project, self.port, self.env = project, port, env
        self.files = ["-f", str(ROOT / "docker" / "compose.yaml"), "-f", str(override)]

    def run(self, *args: str, check: bool = True):
        return docker(
            "compose", *self.files, "-p", self.project, *args,
            check=check, env=self.env, timeout=180,
        )  # fmt: skip


@pytest.fixture
def compose(request, tmp_path) -> Compose:
    """A compose project on a free LADO_PORT, its projects folder a temporary one; taken
    down after the test, its container's logs kept when the test fails."""
    override = tmp_path / "quiet.yaml"
    override.write_text(QUIET_OVERRIDE)
    port = free_port()
    env = {
        **os.environ,
        "LADO_IMAGE": IMAGE,
        # Compose v2 (GitHub's runners) asks for LADO_VERSION also when LADO_IMAGE wins.
        "LADO_VERSION": "test",
        "LADO_PORT": str(port),
        "LADO_PROJECTS": str(tmp_path),
    }
    project = Compose(new_name(), port, override, env)
    # Compose names the service's one container <project>-lado-1.
    keep(request.node, Container(f"{project.project}-lado-1", port))

    def down():
        project.run("down", "-v", check=False)
        # A home volume a test made before `up` (old_home): compose removes only its own.
        docker("volume", "rm", "-f", f"{project.project}_home", check=False)

    request.addfinalizer(down)
    return project


# What a failed test keeps of each container it started, besides `docker logs`.
EVIDENCE = [
    ("lado-ls.txt", "lado ls 2>&1"),
    ("lado-log.txt", "lado log smoke 2>&1"),
    ("hooks.log", "cat ~/.lado/hooks.log 2>&1"),
    ("loop.log", "cat ~/.lado/loop.log 2>&1"),
    ("server.log", "cat ~/.lado/server.log 2>&1"),
    ("endpoint.jsonl", "cat /tmp/endpoint.jsonl 2>&1"),
]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """A test that failed in its setup or call: each container it started, before its
    finalizer removes it, into a folder of real_clis.EVIDENCE named in the report."""
    outcome = yield
    report = outcome.get_result()
    started = item.__dict__.get("lado_containers", [])
    if report.when == "teardown" or not report.failed or not started:
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder = real_clis.EVIDENCE / f"{stamp}-{re.sub(r'[^A-Za-z0-9_.-]', '_', item.name)}"
    try:
        for one in started:
            kept = folder / one.name
            kept.mkdir(parents=True, exist_ok=True)
            (kept / "docker-logs.txt").write_text(one.logs())
            for name, script in EVIDENCE:
                done = one.sh(script, check=False)
                (kept / name).write_text(done.stdout + done.stderr)
        where = f"kept in {folder}"
    except Exception as exc:  # the test's own failure must still be reported
        where = f"could not keep it in {folder}: {exc!r}"
    report.sections.append(("LADO evidence", where))
