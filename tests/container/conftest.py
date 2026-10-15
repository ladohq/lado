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
)


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
def start(request):
    """Start the image as one `docker run` does: `start(port, *args)`, the server on the
    host's `port` by `args`; removed after the test."""

    def start(port: int, *args: str) -> Container:
        started = Container(new_name(), port)
        keep(request.node, started)
        request.addfinalizer(lambda: remove_container(started.name))
        run_container(started.name, *args)
        return started

    return start


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
        "LADO_PORT": str(port),
        "LADO_PROJECTS": str(tmp_path),
    }
    project = Compose(new_name(), port, override, env)
    # Compose names the service's one container <project>-lado-1.
    keep(request.node, Container(f"{project.project}-lado-1", port))
    request.addfinalizer(lambda: project.run("down", "-v", check=False))
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
