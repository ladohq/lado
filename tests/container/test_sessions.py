"""The container's sessions go with it (openspec change container-session-restart): its stop
stops them with a mark, within Docker's grace period, and its start resumes them after the
migration, also after a kill; sessions stopped by hand stay stopped."""

import json
import time

import pytest
from container_helpers import (
    Container,
    claude_session,
    docker,
    fake_endpoint,
    free_port,
    git_repo,
    health,
    on_volume,
    sessions,
    start_claude,
    wait_status,
)
from test_migration import upgraded

pytestmark = pytest.mark.container

STOP_LINE = "lado: the container stops: stopped sessions {}; they resume at its start"
RESUMED = 'lado: resumed session "{}" at the container\'s start'


def wait_line(container: Container, line: str, timeout: float = 120) -> str:
    deadline = time.monotonic() + timeout
    while line not in (logs := container.logs()):
        if time.monotonic() > deadline:
            raise AssertionError(f"no {line!r} in docker logs:\n{logs}")
        time.sleep(0.5)
    return logs


def exit_code(name: str) -> int:
    return json.loads(docker("inspect", name).stdout)[0]["State"]["ExitCode"]


def no_stray_config(container: Container) -> None:
    doctor = container.exec("lado", "doctor", check=False).stdout
    assert "[ok  ] Agent config folders: only those of running agents" in doctor, doctor


def test_compose_stop_and_down_stop_the_session_and_start_and_up_resume_it(compose):
    compose.run("up", "-d")
    health(compose.port)
    container = Container(f"{compose.project}-lado-1", compose.port)
    for repo in ("/home/lado/app", "/home/lado/mine"):
        git_repo(container, repo)
    claude_session(container, "/home/lado/app", "app", "/home/lado/mine")
    start_claude(container, "/home/lado/mine", "mine")
    container.exec("lado", "stop", "mine")  # the human's

    compose.run("stop")
    assert exit_code(container.name) == 0  # ended by its stop, not killed after the grace
    logs = container.logs()
    assert STOP_LINE.format('"app"') in logs, logs
    assert '"mine"' not in logs.split("the container stops")[1].splitlines()[0]
    home = f"{compose.project}_home"
    assert sessions(home) == {"app": (True, True), "mine": (True, False)}

    compose.run("start")
    health(compose.port)
    fake_endpoint(container)
    wait_line(container, RESUMED.format("app"))
    wait_status(container, "app", "supervisor", "idle")
    assert container.agent_status("mine", "supervisor") == "gone"  # stays stopped
    assert RESUMED.format("mine") not in container.logs()
    no_stray_config(container)

    compose.run("down")  # a new container on the same home volume
    assert sessions(home) == {"app": (True, True), "mine": (True, False)}
    compose.run("up", "-d")
    health(compose.port)
    fake_endpoint(container)
    wait_line(container, RESUMED.format("app"))
    wait_status(container, "app", "supervisor", "idle")
    no_stray_config(container)


def test_a_container_killed_resumes_its_session_at_its_start(container):
    git_repo(container, "/home/lado/repo")
    claude_session(container, "/home/lado/repo", "app")
    docker("kill", container.name)
    docker("start", container.name)
    health(container.port)
    fake_endpoint(container)
    logs = wait_line(container, RESUMED.format("app"))
    assert "the container stops" not in logs, logs
    wait_status(container, "app", "supervisor", "idle")
    no_stray_config(container)


def test_three_sessions_stop_within_dockers_default_grace(start):
    port = free_port()
    container = start(port, "-e", f"LADO_PORT={port}", "-p", f"127.0.0.1:{port}:{port}")
    health(port)
    repos = [f"/home/lado/r{n}" for n in range(3)]
    for repo in repos:
        git_repo(container, repo)
    claude_session(container, repos[0], "s0", *repos[1:])
    for n in (1, 2):
        start_claude(container, repos[n], f"s{n}")
    began = time.monotonic()
    docker("stop", container.name, timeout=60)  # Docker's default: ten seconds
    took = time.monotonic() - began
    assert exit_code(container.name) == 0, container.logs()
    assert took < 10, took
    assert STOP_LINE.format('"s0", "s1", "s2"') in container.logs()
    assert sessions(f"{container.name}-home") == {f"s{n}": (True, True) for n in range(3)}


def test_a_new_image_migrates_then_resumes(start, old_home):
    home, before = old_home(running=True)
    on_volume(
        home,
        "git init -q -b main /home/lado/repo && git -C /home/lado/repo -c user.name=lado "
        "-c user.email=lado@example.com commit -q --allow-empty -m first",
    )
    port = free_port()
    container = start(port, "-e", f"LADO_PORT={port}", "-p", f"127.0.0.1:{port}:{port}", home=home)
    health(port)
    logs = wait_line(container, RESUMED.format("old"))
    assert logs.index(upgraded(before)) < logs.index(RESUMED.format("old")), logs
    listed = container.exec("lado", "ls").stdout
    assert "old  /home/lado/repo" in listed and "(stopped)" not in listed, listed
    assert container.agent_status("old", "supervisor") != "gone"
