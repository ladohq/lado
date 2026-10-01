"""Flow runs for real: the fake supervisor starts a run, its worker and the supervisor do
the steps through the MCP tools, LADO delivers each step and cleans up at the end."""

from pathlib import Path

import pytest
from test_agents import SESSION, inputs, lado_cli, supervisor_runs, wait_for, wait_status

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
  check: {gate: approval, ask: 'Go?', outcomes: {approved: end}}
  end: {end: true}
"""


@pytest.fixture
def flow_kit(repo):
    kit = repo / ".lado" / "kits" / "itflow"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: itflow\ninclude: [default]\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    (kit / "flows" / "gated.yaml").write_text(GATED)
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
    wait_for(lambda: got("supervisor", f"flow {name}: waiting for the human at check: Go?"), "wait")
    assert "waiting for human: Go?" in lado_cli("ls").stdout
    result = lado_cli("flow-set", SESSION, name, "end", "--reason", "looks fine")
    assert result.returncode == 0, result.stderr
    assert run_state(name).status == state.ENDED
    assert not Path(run_state(name).worktree).exists()
    assert name not in lado_cli("ls").stdout
