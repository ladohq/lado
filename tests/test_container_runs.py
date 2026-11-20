"""tests/container/container_runs.py: a container test run's lock of its prefix, the start's
reaping of what dead runs left in Docker, and the end's check, with `docker` replaced by a
recorder (the container tests drive the real one)."""

import contextlib
import importlib.util
import signal
import subprocess
import sys
import textwrap
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


container_runs = _load("container_runs", ROOT / "tests" / "container" / "container_runs.py")

DEAD, LIVE, UNKNOWN, OWN = (f"lado-test-{h}-" for h in ("dead01", "11ee11", "abcdef", "0000aa"))


class FakeDocker:
    """`docker` of the container tests: lists from `objects` (kind -> names), removals
    recorded, those in `refuse` failing with docker's words."""

    def __init__(self, objects: dict[str, list[str]], refuse=()):
        self.objects, self.refuse, self.calls = objects, set(refuse), []

    def __call__(self, *args: str, check: bool = True, **kw):
        self.calls.append(args)
        for kind, (ls, rm) in container_runs.KINDS.items():
            if list(args) == ls:
                out = "".join(f"{name}\n" for name in self.objects.get(kind, []))
                return subprocess.CompletedProcess(args, 0, out, "")
            if list(args[: len(rm)]) == rm:
                (name,) = args[len(rm) :]
                if name in self.refuse:
                    return subprocess.CompletedProcess(args, 1, "", f"{name} is in use\n")
                self.objects[kind].remove(name)
                return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(f"unexpected docker {args}")

    def removed(self) -> list[tuple[str, ...]]:
        lists = [ls for ls, _ in container_runs.KINDS.values()]
        return [call for call in self.calls if list(call) not in lists]


@contextlib.contextmanager
def _no_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        yield


@pytest.fixture
def runs(tmp_path, monkeypatch) -> Path:
    folder = tmp_path / "runs"
    monkeypatch.setattr(container_runs, "RUNS", folder)
    return folder


def everything(prefix: str) -> dict[str, list[str]]:
    return {
        "containers": [f"{prefix}c1"],
        "volumes": [f"{prefix}c1-home"],
        "networks": [f"{prefix}p1_default"],
        "tags": [f"{prefix}p1:one"],
    }


def merged(*prefixes: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for prefix in prefixes:
        for kind, names in everything(prefix).items():
            out.setdefault(kind, []).extend(names)
    return out


def held(path: Path):
    """A child process that holds the lock of `path` until its stdin closes."""
    code = textwrap.dedent(
        f"""
        import fcntl, os, sys
        fd = os.open({str(path)!r}, os.O_RDWR | os.O_CREAT)
        fcntl.flock(fd, fcntl.LOCK_EX)
        print("held", flush=True)
        sys.stdin.read()
        """
    )
    child = subprocess.Popen(
        [sys.executable, "-I", "-c", code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert child.stdout.readline() == "held\n"
    return child


def test_objects_are_grouped_by_their_runs_prefix():
    docker = FakeDocker(
        {
            "containers": [f"{DEAD}c1", f"lado-{LIVE}install-lado-1", "someone-else"],
            "volumes": [f"{DEAD}c1-home"],
            "networks": [f"lado-{LIVE}install_default", "bridge"],
            "tags": [f"{DEAD}p1:one"],
        }
    )
    assert container_runs.objects(docker) == {
        DEAD: {
            "containers": [f"{DEAD}c1"],
            "volumes": [f"{DEAD}c1-home"],
            "tags": [f"{DEAD}p1:one"],
        },
        LIVE: {
            "containers": [f"lado-{LIVE}install-lado-1"],
            "networks": [f"lado-{LIVE}install_default"],
        },
    }


def test_a_dead_runs_objects_and_lock_file_are_removed_containers_first(runs):
    runs.mkdir()
    (runs / f"{DEAD}lock").touch()
    docker = FakeDocker(everything(DEAD))
    with _no_warning():
        container_runs.reap(docker, OWN)
    assert docker.removed() == [
        ("rm", "-f", f"{DEAD}c1"),
        ("volume", "rm", "-f", f"{DEAD}c1-home"),
        ("network", "rm", f"{DEAD}p1_default"),
        ("image", "rm", f"{DEAD}p1:one"),
    ]
    assert not (runs / f"{DEAD}lock").exists()


def test_a_lock_file_of_a_run_killed_before_its_first_object_is_removed(runs):
    runs.mkdir()
    (runs / f"{DEAD}lock").touch()
    with _no_warning():
        container_runs.reap(FakeDocker({}), OWN)
    assert not (runs / f"{DEAD}lock").exists()


def test_a_live_runs_objects_are_not_touched(runs):
    runs.mkdir()
    child = held(runs / f"{LIVE}lock")
    try:
        docker = FakeDocker(merged(LIVE, OWN))
        with _no_warning():
            container_runs.reap(docker, OWN)
    finally:
        child.communicate("")
    assert docker.removed() == []
    assert docker.objects == merged(LIVE, OWN)
    assert (runs / f"{LIVE}lock").exists()


def test_objects_of_no_lock_file_are_named_with_their_command_and_kept(runs):
    docker = FakeDocker(everything(UNKNOWN))
    with pytest.warns(UserWarning) as caught:
        container_runs.reap(docker, OWN)
    assert docker.removed() == []
    (message,) = [str(w.message) for w in caught]
    for kind, names in everything(UNKNOWN).items():
        assert f"{kind[:-1]} {names[0]}" in message
    assert (
        f"docker rm -f {UNKNOWN}c1; docker volume rm -f {UNKNOWN}c1-home; "
        f"docker network rm {UNKNOWN}p1_default; docker image rm {UNKNOWN}p1:one"
    ) in message


def test_a_failed_removal_is_named_and_the_lock_file_kept(runs):
    runs.mkdir()
    (runs / f"{DEAD}lock").touch()
    docker = FakeDocker(everything(DEAD), refuse={f"{DEAD}p1_default"})
    with pytest.warns(UserWarning) as caught:
        container_runs.reap(docker, OWN)
    (message,) = [str(w.message) for w in caught]
    assert f"network {DEAD}p1_default: {DEAD}p1_default is in use" in message
    assert f"docker network rm {DEAD}p1_default" in message
    assert docker.objects["volumes"] == [] and docker.objects["tags"] == []
    assert (runs / f"{DEAD}lock").exists()  # a later run tries again


def test_the_runs_own_prefix_is_left_alone(runs):
    lock = container_runs.RunLock(OWN)
    try:
        docker = FakeDocker(everything(OWN))
        with _no_warning():
            container_runs.reap(docker, OWN)
        assert docker.removed() == []
    finally:
        lock.free()


def test_a_runs_lock_is_held_until_freed_and_its_file_deleted(runs):
    lock = container_runs.RunLock(OWN)
    path = runs / f"{OWN}lock"
    probe = (
        "import fcntl, os, sys; fd = os.open(sys.argv[1], os.O_RDWR); "
        "fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)"
    )
    try_lock = [sys.executable, "-I", "-c", probe, str(path)]
    assert subprocess.run(try_lock, capture_output=True).returncode != 0
    lock.free()
    assert not path.exists()


def test_left_names_what_is_left_of_the_runs_own_prefix():
    docker = FakeDocker(merged(OWN, DEAD))
    assert container_runs.left(docker, OWN) == everything(OWN)
    assert container_runs.left(FakeDocker(everything(DEAD)), OWN) == {}


def test_sigterm_and_sighup_raise_keyboard_interrupt_until_restored():
    before = {s: signal.getsignal(s) for s in container_runs.SIGNALS}
    saved = container_runs.trap_signals()
    try:
        for one in container_runs.SIGNALS:
            with pytest.raises(KeyboardInterrupt):
                signal.raise_signal(one)
    finally:
        container_runs.restore_signals(saved)
    assert {s: signal.getsignal(s) for s in container_runs.SIGNALS} == before
