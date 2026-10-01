"""Flow runs for real: the fake supervisor starts a run, its worker and the supervisor do
the steps through the MCP tools, LADO delivers each step and cleans up at the end."""

from pathlib import Path

import pytest
from test_agents import (
    SESSION,
    inputs,
    lado_cli,
    seen,
    supervisor_runs,
    wait_for,
    wait_status,
)

from lado import runtime, state, tmux

pytestmark = pytest.mark.integration

# The fake agents run each line they get as a command: the steps only sleep.
SHIP = """\
name: ship
description: a worker builds it, the supervisor merges it
start: build
states:
  build: {agent: worker, do: sleep 0, outcomes: {done: merge}}
  merge: {agent: supervisor, do: sleep 0, outcomes: {merged: end}}
  end: {end: true}
"""
GATED = """\
name: gated
description: the human says go
start: check
states:
  check: {gate: approval, ask: 'Go?', outcomes: {approved: end, rejected: end}}
  end: {end: true}
"""


REVIEWED = """\
name: reviewed
description: a worker builds it, the human approves it
start: build
states:
  build: {agent: worker, do: sleep 0, outcomes: {done: check}}
  check: {gate: approval, ask: 'Ship it?', outcomes: {approved: end, rejected: build}}
  end: {end: true}
"""


@pytest.fixture
def flow_kit(repo):
    kit = repo / ".lado" / "kits" / "itflow"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: itflow\ninclude: [default]\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    (kit / "flows" / "gated.yaml").write_text(GATED)
    (kit / "flows" / "reviewed.yaml").write_text(REVIEWED)
    runtime.start_session(str(repo), SESSION, None, "fake", ["itflow"])
    wait_status("supervisor", state.IDLE)
    return kit


def got(agent: str, line: str) -> bool:
    return any(line in text for text in inputs(agent))


def run_state(name: str) -> state.Run:
    return state.get_run(SESSION, name)


def test_a_run_goes_from_worker_to_supervisor_to_its_end(repo, flow_kit):
    name = "ship/add-a-file"
    supervisor_runs("flow_start ship add a file")
    wait_for(
        lambda: got("supervisor", f"[from lado] flow {name}: step build needs a worker"), "ask"
    )
    run = run_state(name)
    assert Path(run.worktree, ".git").exists()

    supervisor_runs(f"spawnrun {name}")
    wait_status("w1", state.IDLE)
    worker = state.get_agent(SESSION, "w1")
    assert (worker.cwd, worker.branch, worker.run) == (run.worktree, run.branch, name)
    assert inputs("w1")[0].startswith(f"Run {name} (flow ship), step build.")

    Path(run.worktree, "work.txt").write_text("done\n")
    runtime.git(run.worktree, "add", "work.txt")
    runtime.git(run.worktree, "commit", "-q", "-m", "work")

    runtime.send_message(SESSION, "human", "w1", f"advance {name} bogus")
    wait_for(lambda: 'unknown outcome "bogus"' in tmux.capture(SESSION, "w1"), "the refusal")
    assert run_state(name).state == "build"

    runtime.send_message(SESSION, "human", "w1", f"advance {name} done")
    wait_for(lambda: got("supervisor", f"[from lado] flow {name}: step merge"), "the merge step")
    from_lado = [
        m.summary
        for m in state.list_messages(SESSION)
        if (m.sender, m.recipient) == ("lado", "supervisor")
    ]
    assert from_lado == [f"flow {name}: step build needs a worker", f"flow {name}: step merge"]
    wait_status("supervisor", state.IDLE)

    runtime.git(str(repo), "merge", "-q", "--ff-only", run.branch)
    runtime.send_message(SESSION, "human", "supervisor", f"advance {name} merged")
    ended = f"[from lado] flow {name}: ended at end; worktree and branch removed"
    wait_for(lambda: got("supervisor", ended), "the end")
    assert run_state(name).status == state.ENDED
    assert state.get_agent(SESSION, "w1") is None
    wait_for(lambda: "w1" not in tmux.run("list-windows", "-t", f"={SESSION}"), "w1 closed")
    assert not Path(run.worktree).exists()
    assert runtime.git(str(repo), "branch", "--list", run.branch) == ""
    assert (repo / "work.txt").read_text() == "done\n"
    log = lado_cli("log", SESSION).stdout
    assert f"w1: flow {name} (build -done-> merge)" in log
    assert f"supervisor: flow {name} (merge -merged-> end)" in log
    assert not (state.home() / "hooks.log").exists()


def test_a_run_waits_at_a_gate_until_the_human_sets_it(repo, flow_kit):
    name = "gated/check-it"
    supervisor_runs("flow_start gated check it")
    wait_for(
        lambda: got("supervisor", f"flow {name}: waiting for the human at check (gate #1)"), "wait"
    )
    assert "gate #1 waiting: Go?" in lado_cli("ls").stdout
    result = lado_cli("flow-set", SESSION, name, "end", "--reason", "looks fine")
    assert result.returncode == 0, result.stderr
    assert run_state(name).status == state.ENDED
    assert not Path(run_state(name).worktree).exists()
    assert name not in lado_cli("ls").stdout
    assert "gate #1" not in lado_cli("ls").stdout
    assert (
        f"human: gate_answer {name} (#1 overridden: looks fine)" in lado_cli("log", SESSION).stdout
    )


def to_the_gate(name: str) -> None:
    """Start a run of "reviewed" whose worker reports its build done: the run waits."""
    supervisor_runs("flow_start reviewed check it")
    wait_for(lambda: got("supervisor", f"flow {name}: step build needs a worker"), "ask")
    supervisor_runs(f"spawnrun {name}")
    wait_status("w1", state.IDLE)
    runtime.send_message(SESSION, "human", "w1", f"advance {name} done")
    waiting = f"[from lado] flow {name}: waiting for the human at check (gate #1)"
    wait_for(lambda: got("supervisor", waiting), "the gate")


def test_the_humans_answer_moves_the_run_on_to_the_next_agent(repo, flow_kit):
    name = "reviewed/check-it"
    to_the_gate(name)
    assert "gate #1 waiting: Ship it?" in lado_cli("ls").stdout
    result = lado_cli("answer", SESSION, "1", "reject", "-m", "add a test")
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"gate #1: reject. {name}: check -> build (→ w1)\n"
    step = [m for m in state.list_messages(SESSION) if m.recipient == "w1"][-1]
    assert step.summary == f"flow {name}: step build"
    assert "Note from the previous step: rejected: add a test" in step.body
    wait_for(lambda: got("w1", f"[from lado] flow {name}: step build"), "the step")
    told = f"[from lado] flow {name}: human answered reject at check"
    wait_for(lambda: got("supervisor", told), "the supervisor told")
    log = lado_cli("log", SESSION).stdout
    assert f"lado: gate_open {name} (#1 approval at check: Ship it?)" in log
    assert f"human: gate_answer {name} (#1 reject: add a test)" in log
    assert f"human: flow {name} (check -rejected-> build)" in log


def test_runs_and_gates_survive_stop_and_start(repo, flow_kit):
    ship, gated = "ship/add-a-file", "gated/check-it"
    supervisor_runs("flow_start ship add a file")
    supervisor_runs(f"spawnrun {ship}")
    wait_status("w1", state.IDLE)
    run = run_state(ship)
    Path(run.worktree, "work.txt").write_text("done\n")
    runtime.git(run.worktree, "add", "work.txt")
    runtime.git(run.worktree, "commit", "-q", "-m", "work before the stop")
    supervisor_runs("flow_start gated check it")
    wait_for(lambda: got("supervisor", f"flow {gated}: waiting for the human"), "the gate")
    gate = state.open_gate(SESSION, gated)

    result = lado_cli("stop", SESSION)
    assert result.returncode == 0, result.stderr
    assert not tmux.has_session(SESSION)
    assert f"{SESSION}  {repo}  (stopped)" in lado_cli("ls").stdout

    # `lado start` in-process: the fake provider exists only here. Kits and provider are kept.
    started = runtime.start_session(str(repo), SESSION, None)
    assert (started.resumed, started.changes, started.problems) == (True, [], [])
    resumed = "[from lado] session resumed: 2 open runs"
    wait_for(lambda: any(t.startswith(resumed) for t in inputs("supervisor")), "the resume")
    wait_status("supervisor", state.IDLE)
    supervisor_runs("read")
    # Bodies delivered to the old supervisor and never read come along: the resume is last.
    told = seen("supervisor")["read"][-1]
    assert told["summary"] == "session resumed: 2 open runs"
    assert f'spawn_worker(role="worker", run="{ship}")' in told["body"]
    assert f"lado answer {SESSION} {gate.id}" in told["body"]

    # A new worker takes over the run's worktree and branch, with the earlier commit.
    supervisor_runs(f"spawnrun {ship}")
    wait_status("w1", state.IDLE)
    worker = state.get_agent(SESSION, "w1")
    assert (worker.cwd, worker.branch) == (run.worktree, run.branch)
    assert "work before the stop" in runtime.git(worker.cwd, "log", "--format=%s")
    assert inputs("w1")[-1].startswith(f"Run {ship} (flow ship), step build.")
    runtime.send_message(SESSION, "human", "w1", f"advance {ship} done")
    wait_for(lambda: got("supervisor", f"[from lado] flow {ship}: step merge"), "the merge step")

    # The gate opened before the stop is answered after it.
    result = lado_cli("answer", SESSION, str(gate.id), "approve")
    assert result.returncode == 0, result.stderr
    assert run_state(gated).status == state.ENDED
    log = lado_cli("log", SESSION).stdout
    assert "lado: session_stop" in log and "lado: session_resume" in log
    assert not (state.home() / "hooks.log").exists()


def test_a_popup_asks_the_human_and_never_types_into_an_agent(repo, flow_kit):
    name = "reviewed/check-it"
    # The human's terminal: a tmux client attached to the session.
    attach = ["env", "-u", "TMUX", *tmux.attach_argv(SESSION)]
    tmux.new_session("viewer", "v", str(repo), {}, attach)
    wait_for(lambda: tmux.run("list-clients", "-t", f"={SESSION}").strip(), "the client")
    # The gate opens in w1's MCP server process; it opens the popup.
    to_the_gate(name)
    wait_for(lambda: "1) approve" in tmux.capture("viewer", "v"), "the popup")
    assert "Ship it?" in tmux.capture("viewer", "v")
    tmux.run("send-keys", "-t", "viewer:v", "1", "Enter")
    tmux.run("send-keys", "-t", "viewer:v", "Enter")  # no comment
    wait_for(lambda: run_state(name).status == state.ENDED, "the answer")
    gate = state.get_gate(1)
    assert (gate.answer, gate.answered_by) == ("approve", "human")
    # The popup closes when no gate is left.
    wait_for(lambda: "1) approve" not in tmux.capture("viewer", "v"), "the popup closed")
    assert all(text.strip() != "1" for text in inputs("w1") + inputs("supervisor"))
