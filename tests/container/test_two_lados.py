"""Two LADO containers on one machine update independently (openspec capability container):
each a compose project in a folder of its own, with a copy of docker/compose.yaml and an
.env of its own, as compose.yaml's header says. Updating one, a new image reference in its
.env and `docker compose up -d`, leaves the other's container, start and image as they
were."""

import pytest
from container_helpers import (
    IMAGE,
    Container,
    agent_pid,
    claude_session,
    docker,
    git_repo,
    health,
)

pytestmark = pytest.mark.container


def own_secrets(folder, name: str):
    """A project with a secrets folder of its own (LADO_SECRETS=./secrets, 700), as the
    header enables one: two LADOs never share it."""
    made = folder(name, LADO_SECRETS="./secrets")
    (made.path / "secrets").mkdir(mode=0o700)
    return made


def test_updating_one_lado_leaves_the_other_as_it_is(folder):
    first, second = own_secrets(folder, "first"), own_secrets(folder, "second")
    for each in (first, second):
        each.run("up", "-d")
    for each in (first, second):
        assert health(each.port)["ok"] is True
    before = second.inspect()
    # The update of the first: another image reference in its .env (the same image under
    # another tag of this run's prefix stands for a new version), then `up -d`.
    newer = f"{first.project}:two"
    docker("tag", IMAGE, newer)
    first.settings["LADO_IMAGE"] = newer
    first.write_env()
    first.run("up", "-d")
    assert first.inspect()["Config"]["Image"] == newer
    assert health(first.port)["ok"] is True
    after = second.inspect()
    assert (after["Id"], after["State"]["StartedAt"], after["Config"]["Image"]) == (
        before["Id"],
        before["State"]["StartedAt"],
        before["Config"]["Image"],
    )
    assert health(second.port)["ok"] is True


def test_stopping_one_lado_leaves_the_others_sessions(folder):
    first, second = folder("first"), folder("second")
    containers = []
    for each in (first, second):
        each.run("up", "-d")
        health(each.port)
        container = Container(f"{each.project}-lado-1", each.port)
        git_repo(container, "/home/lado/repo")
        claude_session(container, "/home/lado/repo", "app")
        containers.append(container)
    other = containers[1]
    pid = agent_pid(other, "app", "supervisor")
    first.run("down")
    assert (
        other.exec("tmux", "-L", "lado", "has-session", "-t", "=app", check=False).returncode == 0
    )
    assert agent_pid(other, "app", "supervisor") == pid  # the same process
    assert other.agent_status("app", "supervisor") == "idle"
    stopped = other.python(
        "from lado import state; print([s.name for s in state.list_sessions() if s.stopped_at])"
    )
    assert stopped == "[]"
    assert "the container stops" not in other.logs()
