"""Flow runs for real: the fake supervisor starts a run, its worker and the supervisor do
the steps through the MCP tools, LADO delivers each step and cleans up at the end."""

import re
import sys
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

from lado import artifacts, runs, runtime, state, tmux

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


TINY = """\
name: tiny
description: a worker does it
start: build
states:
  build: {agent: worker, do: sleep 0, outcomes: {done: end}}
  end: {end: true}
"""


PLANNED = """\
name: planned
description: the supervisor plans it, a worker builds it
start: plan
states:
  plan: {agent: supervisor, do: sleep 0, outcomes: {ready: build}}
  build: {agent: worker, do: sleep 0, outcomes: {done: end}}
  end: {end: true}
"""


DESIGNED = """\
name: designed
description: the supervisor designs it, the human approves, a worker builds it
start: design
states:
  design: {agent: supervisor, do: sleep 0, produces: [design], outcomes: {ready: approve}}
  approve: {gate: approval, ask: 'Build it?', outcomes: {approved: build, rejected: design}}
  build: {agent: worker, do: sleep 0, reads: [design], outcomes: {done: end}}
  end: {end: true}
"""


PRODUCED = """\
name: produced
description: a worker writes its report, the human approves it
start: build
states:
  build: {agent: worker, do: sleep 0, produces: [report], outcomes: {done: check}}
  check: {gate: approval, ask: 'Ship it?', outcomes: {approved: end, rejected: build}}
  end: {end: true}
"""


@pytest.fixture
def flow_kit(repo):
    kit = repo / ".lado" / "kits" / "itflow"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: itflow\nversion: 1.0.0\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    (kit / "flows" / "gated.yaml").write_text(GATED)
    (kit / "flows" / "reviewed.yaml").write_text(REVIEWED)
    (kit / "flows" / "planned.yaml").write_text(PLANNED)
    (kit / "flows" / "tiny.yaml").write_text(TINY)
    (kit / "flows" / "designed.yaml").write_text(DESIGNED)
    (kit / "flows" / "produced.yaml").write_text(PRODUCED)
    runtime.start_session(str(repo), SESSION, None, "fake", ["default", "itflow"])
    wait_status("supervisor", state.IDLE)
    return kit


def got(agent: str, line: str) -> bool:
    return any(line in text for text in inputs(agent))


def run_state(name: str) -> state.Run:
    return state.get_run(SESSION, name)


def test_a_run_goes_from_worker_to_supervisor_to_its_end(repo, flow_kit):
    name = "ship/add-a-file"
    supervisor_runs("flow_start ship add a file")
    # The supervisor caused it: it hears in the tool's result, not in a message.
    [ask] = seen("supervisor")["flow_start"]["notices"]
    assert ask.startswith(f"flow {name}: step build needs a worker\n")
    run = run_state(name)
    assert Path(run.worktree, ".git").exists()

    supervisor_runs(f"spawnrun {name}")
    wait_status("worker", state.IDLE)
    worker = state.get_agent(SESSION, "worker")
    assert (worker.cwd, worker.branch, worker.run) == (run.worktree, run.branch, name)
    assert inputs("worker")[0].startswith(f"Run {name} (flow ship), step build.")

    Path(run.worktree, "work.txt").write_text("done\n")
    runtime.git(run.worktree, "add", "work.txt")
    runtime.git(run.worktree, "commit", "-q", "-m", "work")

    runtime.send_message(SESSION, "human", "worker", f"advance {name} bogus")
    wait_for(lambda: 'unknown outcome "bogus"' in tmux.capture(SESSION, "worker"), "the refusal")
    assert run_state(name).state == "build"

    runtime.send_message(SESSION, "human", "worker", f"advance {name} done")
    wait_for(lambda: got("supervisor", f"[from lado] flow {name}: step merge"), "the merge step")
    from_lado = [
        m.summary
        for m in state.list_messages(SESSION)
        if (m.sender, m.recipient) == ("lado", "supervisor")
    ]
    assert from_lado == [f"flow {name}: step merge"]
    wait_status("supervisor", state.IDLE)

    runtime.git(str(repo), "merge", "-q", "--ff-only", run.branch)
    supervisor_runs(f"advance {name} merged")
    ended = f"flow {name}: ended at end; worktree and branch removed"
    assert seen("supervisor")["advance"]["notices"] == [ended]
    assert [m.summary for m in state.list_messages(SESSION) if m.sender == "lado"] == [
        f"flow {name}: step merge"
    ]
    assert run_state(name).status == state.ENDED
    # Each flow_advance through MCP kept its step: who reported it, the outcome, where to.
    steps = [(n.state, n.actor, n.outcome, n.target) for n in state.run_notes(SESSION, name)]
    assert steps == [("build", "worker", "done", "merge"), ("merge", "supervisor", "merged", "end")]
    assert state.get_agent(SESSION, "worker") is None
    wait_for(
        lambda: "worker" not in tmux.run("list-windows", "-t", f"={SESSION}"), "the worker closed"
    )
    assert not Path(run.worktree).exists()
    assert runtime.git(str(repo), "branch", "--list", run.branch) == ""
    assert (repo / "work.txt").read_text() == "done\n"
    log = lado_cli("log", SESSION).stdout
    assert f"worker: flow {name} (build -done-> merge)" in log
    assert f"supervisor: flow {name} (merge -merged-> end)" in log
    assert not (state.home() / "hooks.log").exists()


def test_the_supervisor_hears_when_a_worker_ends_the_run(repo, flow_kit):
    # Started and spawned from outside, as `lado` or the live test does: no notices.
    name = "tiny/do-it"
    runs.start(SESSION, "tiny", "do it")
    runs.spawn_worker(SESSION, name, name="worker")
    wait_status("worker", state.IDLE)
    run = run_state(name)
    Path(run.worktree, "work.txt").write_text("done\n")
    runtime.git(run.worktree, "add", "work.txt")
    runtime.git(run.worktree, "commit", "-q", "-m", "work")

    runtime.send_message(SESSION, "human", "worker", f"advance {name} done")
    # The worker's MCP server stores the end first and tells the supervisor after its git checks.
    kept = f"[from lado] flow {name}: ended at end; kept its worktree and branch"
    wait_for(lambda: any(t.startswith(kept) for t in inputs("supervisor")), "the end told")
    assert run_state(name).status == state.ENDED
    wait_for(lambda: "advance" in seen("worker"), "the worker's result")
    assert seen("worker")["advance"]["notices"] == []
    assert state.get_agent(SESSION, "worker") is not None


def test_a_worker_gets_a_step_far_longer_than_a_tmux_command(repo, flow_kit):
    # tmux refuses a command over about 16 KB; the first message used to be on it.
    name = "planned/long"
    runs.start(SESSION, "planned", "a long plan", name="long", notices=[])
    plan = "\n".join(f"plan line {n}: " + "x" * 60 for n in range(800))  # about 60 KB
    runs.advance(SESSION, "supervisor", name, "ready", "planned", plan, notices=[])
    worker = runs.spawn_worker(SESSION, name)
    wait_status("worker", state.IDLE)
    step = runs.step_text(run_state(name), runs.flow_of(run_state(name)))
    assert worker.task == step  # still the worker's task, in full
    [first] = inputs("worker")
    line = r"\[from lado\] flow planned/long: step build \(#\d+, \d+ lines: call read_messages\)"
    assert re.fullmatch(line, first)
    runtime.send_message(SESSION, "human", "worker", "read")
    wait_for(lambda: "read" in seen("worker"), "the worker to read")
    [got_step] = seen("worker")["read"]
    assert got_step["body"] == step


def test_a_run_waits_at_a_gate_until_the_human_sets_it(repo, flow_kit):
    name = "gated/check-it"
    supervisor_runs("flow_start gated check it")
    [waiting] = seen("supervisor")["flow_start"]["notices"]
    assert waiting.startswith(f"flow {name}: waiting for the human at check (gate #1)\n")
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


def test_a_step_is_refused_until_it_writes_what_it_produces(repo, flow_kit):
    name = "produced/report-it"
    supervisor_runs("flow_start produced report it")
    supervisor_runs(f"spawnrun {name}")
    wait_status("worker", state.IDLE)
    assert "This step must write: report (write_artifact)" in inputs("worker")[0]

    runtime.send_message(SESSION, "human", "worker", f"advance {name} done")
    refusal = "step build must write report before flow_advance"
    # The line is wrapped between words: joined again.
    wait_for(lambda: refusal in " ".join(tmux.capture(SESSION, "worker").split()), "the refusal")
    assert run_state(name).state == "build"
    assert state.run_notes(SESSION, name) == []

    Path(run_state(name).worktree, "report.md").write_text("# Report\n")
    runtime.send_message(SESSION, "human", "worker", "artifact_write report report.md")
    wait_for(lambda: "artifact_write" in seen("worker"), "the report written")
    runtime.send_message(SESSION, "human", "worker", f"advance {name} done reported")
    wait_for(lambda: run_state(name).state == "check", "the gate")
    [note] = state.run_notes(SESSION, name)
    report = artifacts.find(SESSION, f"{name}/report")
    assert state.note_attachments(note.id) == [(report[0].id, report[1].id)]
    gate = state.open_gate(SESSION, name)
    assert runs.gate_artifacts(gate) == f"Artifacts: {name}/report"


def to_the_gate(name: str) -> None:
    """Start a run of "reviewed" whose worker reports its build done: the run waits."""
    supervisor_runs("flow_start reviewed check it")
    supervisor_runs(f"spawnrun {name}")
    wait_status("worker", state.IDLE)
    runtime.send_message(SESSION, "human", "worker", f"advance {name} done")
    waiting = f"[from lado] flow {name}: waiting for the human at check (gate #1)"
    wait_for(lambda: got("supervisor", waiting), "the gate")


def test_the_humans_answer_moves_the_run_on_to_the_next_agent(repo, flow_kit):
    name = "reviewed/check-it"
    to_the_gate(name)
    assert "gate #1 waiting: Ship it?" in lado_cli("ls").stdout
    result = lado_cli("answer", SESSION, "1", "reject", "-m", "add a test")
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"gate #1: reject. {name}: check -> build (→ worker)\n"
    step = [m for m in state.list_messages(SESSION) if m.recipient == "worker"][-1]
    assert step.summary == f"flow {name}: step build"
    assert "Note from the previous step: rejected: add a test" in step.body
    wait_for(lambda: got("worker", f"[from lado] flow {name}: step build"), "the step")
    told = f"[from lado] flow {name}: human answered reject at check"
    wait_for(lambda: got("supervisor", told), "the supervisor told")
    log = lado_cli("log", SESSION).stdout
    assert f"lado: gate_open {name} (#1 approval at check: Ship it?)" in log
    assert f"human: gate_answer {name} (#1 reject: add a test)" in log
    assert f"human: flow {name} (check -rejected-> build)" in log


def test_a_step_gets_the_artifact_it_reads_after_a_gate_and_after_flow_set(repo, flow_kit):
    name = "designed/build-it"
    supervisor_runs("flow_start designed build it")
    (repo / "design.md").write_text("# Design\n\nuse a form, no captcha\n")
    supervisor_runs(f"artifact_write {name}/design design.md")
    supervisor_runs(f"advance {name} ready the design")
    assert run_state(name).status == state.WAITING
    result = lado_cli("answer", SESSION, "1", "approve", "-m", "go")
    assert result.returncode == 0, result.stderr
    supervisor_runs(f"spawnrun {name}")
    wait_status("worker", state.IDLE)
    # The worker's run's scope: the bare name, never the content.
    design = "Artifacts this step reads (read each with read_artifact):\n- design"
    [first] = inputs("worker")
    assert first.startswith(f"Run {name} (flow designed), step build.")
    assert design in first
    assert "no captcha" not in first
    assert "Note from the previous step: approved: go" in first

    # Set back to build by the human: the previous note is the reason, the design stays.
    result = lado_cli("flow-set", SESSION, name, "build", "--reason", "once more")
    assert result.returncode == 0, result.stderr
    wait_for(lambda: got("worker", f"[from lado] flow {name}: step build"), "the step again")
    step = [m for m in state.list_messages(SESSION) if m.recipient == "worker"][-1]
    assert design in step.body
    assert "Note from the previous step: set by the human: once more" in step.body


def test_runs_and_gates_survive_stop_and_start(repo, flow_kit):
    ship, gated = "ship/add-a-file", "gated/check-it"
    supervisor_runs("flow_start ship add a file")
    supervisor_runs(f"spawnrun {ship}")
    wait_status("worker", state.IDLE)
    run = run_state(ship)
    Path(run.worktree, "work.txt").write_text("done\n")
    runtime.git(run.worktree, "add", "work.txt")
    runtime.git(run.worktree, "commit", "-q", "-m", "work before the stop")
    supervisor_runs("flow_start gated check it")
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
    # Bodies the old supervisor never read were dropped at the stop: it starts fresh.
    [told] = seen("supervisor")["read"]
    assert told["summary"] == "session resumed: 2 open runs"
    assert f'spawn_worker(role="worker", run="{ship}")' in told["body"]
    assert f"lado answer {SESSION} {gate.id}" in told["body"]

    # A new worker takes over the run's worktree and branch, with the earlier commit.
    supervisor_runs(f"spawnrun {ship}")
    wait_status("worker", state.IDLE)
    worker = state.get_agent(SESSION, "worker")
    assert (worker.cwd, worker.branch) == (run.worktree, run.branch)
    assert "work before the stop" in runtime.git(worker.cwd, "log", "--format=%s")
    assert inputs("worker")[-1].startswith(f"Run {ship} (flow ship), step build.")
    runtime.send_message(SESSION, "human", "worker", f"advance {ship} done")
    wait_for(lambda: got("supervisor", f"[from lado] flow {ship}: step merge"), "the merge step")

    # The gate opened before the stop is answered after it.
    result = lado_cli("answer", SESSION, str(gate.id), "approve")
    assert result.returncode == 0, result.stderr
    assert run_state(gated).status == state.ENDED
    log = lado_cli("log", SESSION).stdout
    assert "lado: session_stop" in log and "lado: session_resume" in log
    assert not (state.home() / "hooks.log").exists()


def test_lado_answer_ends_when_its_gate_is_answered_elsewhere(repo, flow_kit):
    """The popup's `lado answer` waits for the human; the gate is answered in another
    process (the UI's server, another popup): it says so and ends, and what the human had
    typed goes nowhere."""
    name = runs.start(SESSION, "gated", "check it").name  # it starts at its gate, #1
    env = [f"LADO_HOME={state.home()}", f"LADO_TMUX_SOCKET={tmux.socket()}"]
    answer = f"{sys.executable} -m lado.cli answer {SESSION} 1; echo exited $?; sleep 600"
    tmux.new_session("asking", "a", str(repo), ["env", *env, "sh", "-c", answer])
    wait_for(lambda: "Answer (number or name" in tmux.capture("asking", "a"), "the question")
    tmux.run("send-keys", "-t", "asking:a", "-l", "appr")  # typing, no Enter yet
    result = lado_cli("answer", SESSION, "1", "reject", "-m", "add a test")
    assert result.returncode == 0, result.stderr
    wait_for(lambda: "exited 0" in tmux.capture("asking", "a"), "lado answer to end")
    screen = tmux.capture("asking", "a")
    assert "Gate #1 was answered elsewhere: reject by human\nNo more open gates.\n" in screen
    assert "no option" not in screen
    # The other process's answer, not what was typed here; "gated" ends either way.
    assert state.get_gate(1).answer == "reject"
    assert (run_state(name).state, run_state(name).status) == ("end", state.ENDED)


def test_a_popup_asks_the_human_and_never_types_into_an_agent(repo, flow_kit):
    name = "reviewed/check-it"
    # The human's terminal: a tmux client attached to the session.
    attach = ["env", "-u", "TMUX", *tmux.attach_argv(SESSION)]
    tmux.new_session("viewer", "v", str(repo), attach)
    wait_for(lambda: tmux.run("list-clients", "-t", f"={SESSION}").strip(), "the client")
    # The gate opens in the worker's MCP server process; it opens the popup.
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
    assert all(text.strip() != "1" for text in inputs("worker") + inputs("supervisor"))
