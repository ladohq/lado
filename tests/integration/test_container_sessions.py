"""The UI server in LADO's container stops the sessions at its end and resumes them at its
start (openspec change container-session-restart): a real `lado server` with
LADO_CONTAINER=1, real tmux, hooks, `lado mcp` and SQLite, and the fake agent."""

import os
import shutil
import signal
import subprocess
import sys

import fake_provider
import pytest
from agent_helpers import fake_logs, init_repo, install_kit, wait_for

from lado import loop, runs, runtime, state, tmux
from lado.server import run as server_run

pytestmark = pytest.mark.integration

TINY = """\
name: tiny
description: a worker does it
start: build
states:
  build: {agent: worker, do: sleep 0, outcomes: {done: end}}
  end: {end: true}
"""
STOP_LINE = "lado: the container stops: stopped sessions {}; they resume at its start"
RESUMED = 'lado: resumed session "{}" at the container\'s start'


class Server:
    """`lado server` as the container runs it, in a process of its own; its stderr in a
    file. The fake providers are known to it (fake_provider.py as `lado`)."""

    def __init__(self, err, container: bool = True):
        env = dict(os.environ)
        if container:
            env["LADO_CONTAINER"] = "1"
        else:
            env.pop("LADO_CONTAINER", None)
        self.err = err
        self.start_at = err.stat().st_size if err.exists() else 0
        with open(err, "a") as out:
            self.process = subprocess.Popen(
                [sys.executable, str(fake_provider.LADO), "server", "--port", "0"],
                stdout=subprocess.DEVNULL,
                stderr=out,
                env=env,
            )
        server_run.wait_ready()

    def said(self) -> str:
        with open(self.err) as text:
            text.seek(self.start_at)
            return text.read()

    def stop(self, sig: int = signal.SIGTERM) -> int:
        self.process.send_signal(sig)
        return self.process.wait(timeout=30)


@pytest.fixture
def server(tmp_path):
    started = []

    def start(container: bool = True) -> Server:
        started.append(Server(tmp_path / "server.err", container))
        return started[-1]

    yield start
    for each in started:
        if each.process.poll() is None:
            each.stop()


def idle(session: str) -> bool:
    agent = state.get_agent(session, "supervisor")
    return agent is not None and agent.status == state.IDLE


def wait_idle(session: str, agent: str = "supervisor") -> None:
    def ready():
        found = state.get_agent(session, agent)
        return found is not None and found.status == state.IDLE

    wait_for(ready, f"{agent} of {session} idle", session)


def start(repo, name: str, kits=None) -> None:
    runtime.start_session(str(repo), name, None, "fake", kits)
    wait_idle(name)


def loop_ended(session: str) -> None:
    wait_for(lambda: not loop.running(session), f"the loop of {session} to end", session)


@pytest.fixture
def flow_kit(repo):
    kit = repo.parent / "kits" / "itflow"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: itflow\nversion: 1.0.0\n")
    (kit / "flows" / "tiny.yaml").write_text(TINY)
    install_kit(kit)
    return kit


def test_the_container_stops_its_sessions_and_resumes_them_at_its_start(
    repo, server, flow_kit, lado_home, monkeypatch
):
    monkeypatch.setenv("FAKE_AGENT_HANGUP_HOOK", "1")  # killed, it ends with its hook
    start(repo, "s", ["default", "itflow"])
    runs.start("s", "tiny", "do it", notices=[])
    runs.spawn_worker("s", "tiny/do-it", name="worker")
    wait_idle("s", "worker")
    start(repo, "mine")
    runtime.stop_session("mine")  # the human's
    loop_ended("mine")
    first = server()
    last = max(m.id for m in state.list_messages("s"))

    assert first.stop() == 0
    assert STOP_LINE.format('"s"') in first.said()
    assert '"mine"' not in first.said()
    sess = state.get_session("s")
    assert sess.stopped_at and sess.resume_at_start
    assert not tmux.has_session("s")
    assert not (lado_home / "agents" / "s").exists()
    loop_ended("s")
    told = [m for m in state.list_messages("s") if m.id > last and m.sender == state.LADO]
    assert told == []  # nothing about the dying agents
    [stop] = [e for e in state.list_events("s") if e.kind == state.SESSION_STOP]
    assert stop.detail.endswith("; the container stopped")

    second = server()
    wait_for(lambda: idle("s"), "the resumed supervisor idle", "s")
    wait_for(lambda: RESUMED.format("s") in second.said(), "the resumed line", "s")
    assert not state.get_session("s").resume_at_start
    assert state.get_session("mine").stopped_at  # stays stopped
    assert '"mine"' not in second.said()
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]  # no worker restarted
    resumed = [m for m in state.list_messages("s") if m.id > last and m.sender == state.LADO]
    assert resumed[0].summary == "session resumed: 1 open run"
    assert "spawn_worker" in resumed[0].body
    [event] = [e for e in state.list_events("s") if e.kind == state.SESSION_RESUME]
    assert event.detail == "at the container's start; same settings"
    assert runtime.stray_config_dirs() == []
    assert second.stop() == 0
    loop_ended("s")


def test_a_container_killed_without_its_stop_resumes_its_sessions(repo, server):
    start(repo, "s")
    first = server()
    tmux.kill_session("s")  # the container's end takes its processes
    assert first.stop(signal.SIGKILL) == -signal.SIGKILL
    loop_ended("s")
    assert not state.get_session("s").stopped_at  # nothing marked it

    second = server()
    wait_for(lambda: RESUMED.format("s") in second.said(), "the resumed line", "s")
    wait_for(lambda: idle("s"), "the resumed supervisor idle", "s")
    kinds = [e.kind for e in state.list_events("s")]
    assert state.SESSION_GONE in kinds
    assert second.stop() == 0
    loop_ended("s")


def test_a_resume_that_fails_is_not_tried_again(repo, tmp_path, server):
    elsewhere = init_repo(tmp_path / "elsewhere")
    start(elsewhere, "lost")
    start(repo, "s")
    assert server().stop() == 0
    loop_ended("lost")
    loop_ended("s")
    shutil.rmtree(elsewhere)

    second = server()
    wait_for(lambda: RESUMED.format("s") in second.said(), "the resumed line", "s")
    failed = 'lado: could not resume session "lost" at the container\'s start: '
    assert failed in second.said()
    assert second.said().split(failed)[1].splitlines()[0].endswith("; it stays stopped")
    lost = state.get_session("lost")
    assert lost.stopped_at and not lost.resume_at_start
    assert second.stop() == 0
    loop_ended("s")

    third = server()
    wait_for(lambda: RESUMED.format("s") in third.said(), "the resumed line", "s")
    assert '"lost"' not in third.said()
    assert third.stop() == 0
    loop_ended("s")


def test_outside_a_container_the_server_leaves_the_sessions(repo, server):
    start(repo, "s")
    assert server(container=False).stop() == 0
    assert tmux.has_session("s")
    assert not state.get_session("s").stopped_at
    instance = state.get_agent("s", "supervisor").instance
    second = server(container=False)
    assert second.stop() == 0
    assert "resume" not in second.said()
    assert state.get_agent("s", "supervisor").instance == instance  # the same launch
    assert fake_logs("s", "supervisor").exists()
    runtime.stop_session("s")
