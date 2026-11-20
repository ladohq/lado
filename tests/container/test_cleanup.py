"""A container test run stopped from outside: SIGTERM ends it through the finalizers with
nothing of its prefix left in Docker; after a SIGKILL, the next run's reaping removes what
it left; a prefix of no lock file is only named (container_runs)."""

import os
import secrets
import signal
import subprocess
import sys
import time
import warnings

import container_runs
import pytest
from container_helpers import ROOT, docker

pytestmark = pytest.mark.container

KINDS = {"containers", "volumes", "networks", "tags"}


@pytest.fixture
def runs(tmp_path, monkeypatch):
    """The lock folder of this test and of its child runs, so the reaping here meets only
    their locks: every other prefix in Docker is one of no lock file there, named, never
    removed."""
    folder = tmp_path / "runs"
    monkeypatch.setattr(container_runs, "RUNS", folder)
    return folder


def child_run(tmp_path, runs):
    """A run of cleanup_target.py, a session of its own, once its objects are made: the
    process and its prefix."""
    ready = tmp_path / "ready"
    env = {**os.environ, "LADO_CONTAINER_RUNS": str(runs), "LADO_CLEANUP_READY": str(ready)}
    log = (tmp_path / "child.log").open("w")
    child = subprocess.Popen(
        [
            sys.executable, "-m", "pytest", "-m", "container", "-n0", "-p", "no:cacheprovider",
            "-q", "tests/container/cleanup_target.py",
        ],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
    )  # fmt: skip
    deadline = time.monotonic() + 420
    while not ready.exists() or not ready.read_text():
        if child.poll() is not None or time.monotonic() > deadline:
            child.kill()
            child.wait()
            raise AssertionError(f"the child run did not get ready:\n{output(tmp_path)}")
        time.sleep(0.5)
    prefix = ready.read_text()
    made = container_runs.left(docker, prefix)
    assert set(made) == KINDS, f"the child made only {made}"
    return child, prefix


def output(tmp_path) -> str:
    return (tmp_path / "child.log").read_text(errors="replace")


def remove(prefix: str) -> None:
    """Whatever a failed case left of `prefix`, so the test's own run ends clean."""
    for kind, names in container_runs.left(docker, prefix).items():
        for name in names:
            docker(*container_runs.KINDS[kind][1], name, check=False)


def test_sigterm_ends_the_run_through_its_finalizers(tmp_path, runs):
    child, prefix = child_run(tmp_path, runs)
    try:
        child.send_signal(signal.SIGTERM)
        code = child.wait(timeout=300)
        assert code == pytest.ExitCode.INTERRUPTED, output(tmp_path)
        assert container_runs.left(docker, prefix) == {}, output(tmp_path)
        assert not (runs / f"{prefix}lock").exists()
    finally:
        child.kill()
        child.wait()
        remove(prefix)


def test_the_next_run_reaps_what_a_sigkill_left(tmp_path, runs):
    child, prefix = child_run(tmp_path, runs)
    try:
        child.kill()
        child.wait()
        assert set(container_runs.left(docker, prefix)) == KINDS
        assert (runs / f"{prefix}lock").exists()
        with warnings.catch_warnings(record=True):  # other prefixes of Docker are named
            warnings.simplefilter("always")
            container_runs.reap(docker, "lado-test-000000-")
        assert container_runs.left(docker, prefix) == {}
        assert not (runs / f"{prefix}lock").exists()
    finally:
        remove(prefix)


def test_a_prefix_of_no_lock_file_is_named_and_kept(runs):
    volume = f"lado-test-{secrets.token_hex(3)}-x"
    docker("volume", "create", volume)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            container_runs.reap(docker, "lado-test-000000-")
        (message,) = [str(w.message) for w in caught]
        assert f"volume {volume}" in message
        assert volume in message.split("remove them with: ")[1]
        assert docker("volume", "inspect", volume, check=False).returncode == 0
    finally:
        docker("volume", "rm", "-f", volume, check=False)
