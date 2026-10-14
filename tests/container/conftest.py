"""Container tests: LADO's image (docker/Dockerfile) with real Docker and no model. They drive
the `docker` CLI from the host against an image built already (`make docker`;
`LADO_TEST_IMAGE`, else lado:local) and skip when Docker does not run or the image is
missing; CI's cell (scripts/smoke_ci.py container) makes a skip red.

Each test's containers, volumes and compose projects are named lado-test-<hex> and removed
after it, also when it fails; a failed test keeps the container's logs and LADO's logs in
real_clis.EVIDENCE, as a failed smoke test does.
"""

import re
import secrets
import shutil
import time

import pytest
import real_clis
from container_helpers import (
    IMAGE,
    PREFIX,
    Container,
    docker,
    free_port,
    health,
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
    left = docker("ps", "-a", "-q", "--filter", f"name={PREFIX}").stdout.split()
    assert left == [], f"containers left behind: {left}"


@pytest.fixture
def container():
    """The image as one `docker run` starts it, on a free port other than 8765."""
    name, port = f"{PREFIX}{secrets.token_hex(4)}", free_port()
    run_container(name, "-e", f"LADO_PORT={port}", "-p", f"127.0.0.1:{port}:{port}")
    try:
        health(port)
        yield Container(name, port)
    finally:
        remove_container(name)


# What a failed test keeps of its container, besides `docker logs`.
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
    """A failed test's container, before its fixture removes it: its logs and LADO's into a
    folder of real_clis.EVIDENCE, named in the report."""
    outcome = yield
    report = outcome.get_result()
    started = getattr(item, "funcargs", {}).get("container")
    if report.when != "call" or not report.failed or not isinstance(started, Container):
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder = real_clis.EVIDENCE / f"{stamp}-{re.sub(r'[^A-Za-z0-9_.-]', '_', item.name)}"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "docker-logs.txt").write_text(started.logs())
        for name, script in EVIDENCE:
            (folder / name).write_text(started.sh(script, check=False).stdout)
        kept = f"kept in {folder}"
    except Exception as exc:  # the test's own failure must still be reported
        kept = f"could not keep it in {folder}: {exc!r}"
    report.sections.append(("LADO evidence", kept))
