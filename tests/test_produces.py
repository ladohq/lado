"""A work state's `produces`: the artifacts its step must write before an outcome is taken
(docs/design/artifacts.md, Flows)."""

import pytest

from lado import artifacts, artifacts_local, runs, runtime, state
from lado.runtime import LadoError
from lado.server import models

SHIP = """\
name: ship
description: build it, the human approves, the lead wraps it up
start: build
states:
  build:
    agent: worker
    do: Build it.
    produces: [design]
    outcomes: {done: approve, again: build}
  approve:
    gate: approval
    ask: "Ship it?"
    outcomes: {approved: wrap, rejected: build}
  wrap:
    agent: supervisor
    do: Wrap it up.
    reads: [design]
    produces: [summary]
    outcomes: {done: end}
  end: {end: true}
"""


@pytest.fixture
def run(repo, fake_tmux):
    kit = repo / ".lado" / "kits" / "k"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: k\nversion: 1.0.0\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    runtime.start_session(str(repo), "s", None, kit_names=["default", "k"], provider="claude")
    runs.start("s", "ship", "Add x", name="x")
    runs.spawn_worker("s", "ship/x")
    return "ship/x"


def _advance(caller, outcome, **kwargs):
    return runs.advance("s", caller, "ship/x", outcome, **kwargs)


def _to_wrap():
    """Through build and the gate to the lead's step."""
    artifacts.write("s", "worker", "design", content="d1")
    _advance("worker", "done", note="built")
    runs.answer("s", str(state.open_gate("s", "ship/x").id), "approve")
    assert state.get_run("s", "ship/x").state == "wrap"


def _unmoved(before):
    after = state.get_run("s", "ship/x")
    assert (after.state, after.visits, after.status) == (
        before.state,
        before.visits,
        before.status,
    )
    assert state.run_notes("s", "ship/x") == []


def test_a_step_that_did_not_write_its_artifact_is_refused_by_the_name_the_worker_writes(run):
    before = state.get_run("s", run)
    with pytest.raises(LadoError) as refused:
        _advance("worker", "done")
    assert str(refused.value) == (
        "step build must write design before flow_advance; "
        'write each with write_artifact(name="design", ...)'
    )
    _unmoved(before)


def test_the_lead_is_told_the_full_name(run):
    _to_wrap()
    with pytest.raises(LadoError, match=r'write_artifact\(name="ship/x/summary", \.\.\.\)'):
        _advance("supervisor", "done")
    assert state.get_run("s", run).state == "wrap"


def test_a_write_in_this_visit_counts_and_is_attached_to_the_note(run):
    written = artifacts.write("s", "worker", "design", content="d1")
    _advance("worker", "done", note="built")
    note = state.last_note("s", run)
    assert state.note_attachments(note.id) == [(written.artifact.id, written.record.id)]


def test_the_counted_record_comes_first_and_an_attachment_of_the_same_artifact_once(run):
    artifacts.write("s", "worker", "plan", content="p1")
    counted = artifacts.write("s", "worker", "design", content="d1")
    _advance("worker", "done", attached=["plan", "design", "ship/x/design"])
    attached = state.note_attachments(state.last_note("s", run).id)
    assert attached[0] == (counted.artifact.id, counted.record.id)
    assert [artifact for artifact, _ in attached] == [
        counted.artifact.id,
        artifacts.find("s", "ship/x/plan")[0].id,
    ]


def test_a_write_of_a_previous_visit_does_not_count_and_one_unchanged_does(run):
    artifacts.write("s", "worker", "design", content="d1")
    _advance("worker", "again")
    assert state.get_run("s", run).visits["build"] == 2
    with pytest.raises(LadoError, match="must write design"):
        _advance("worker", "done")
    again = artifacts.write("s", "worker", "design", content="d1")
    assert again.unchanged
    _advance("worker", "done")
    assert state.get_run("s", run).state == "approve"


def test_a_write_before_a_flow_set_does_not_count(run):
    artifacts.write("s", "worker", "design", content="d1")
    runs.force("s", run, "build", "start over")
    with pytest.raises(LadoError, match="must write design"):
        _advance("worker", "done")


def test_a_write_of_another_state_does_not_count(run):
    # Written by the run's worker in build, the first visit of build and of wrap alike.
    artifacts.write("s", "worker", "summary", content="early")
    _to_wrap()
    with pytest.raises(LadoError, match="must write ship/x/summary"):
        _advance("supervisor", "done")


def test_a_write_in_the_sessions_scope_or_another_runs_does_not_count(run):
    _to_wrap()
    runs.start("s", "ship", "Add y", name="y")
    artifacts.write("s", "supervisor", "summary", content="in the session")
    artifacts.write("s", "supervisor", "ship/y/summary", content="in another run")
    with pytest.raises(LadoError, match="must write ship/x/summary"):
        _advance("supervisor", "done")
    artifacts.write("s", "supervisor", "ship/x/summary", content="here")
    _advance("supervisor", "done")
    assert state.get_run("s", run).status == state.ENDED


def test_a_latest_record_not_of_this_visit_refuses_also_after_one_that_was(run):
    # A writer that read the run before it entered the state: its record is the latest.
    artifacts.write("s", "worker", "design", content="d1")
    found = artifacts.store().latest("s", run, "design")
    artifacts.store().write(
        "s",
        run,
        "design",
        b"late",
        "text/markdown",
        author="worker",
        run=run,
        state="approve",
        visit=1,
        summary=None,
        title=None,
    )
    assert found is not None
    with pytest.raises(LadoError, match="must write design"):
        _advance("worker", "done")


@pytest.mark.parametrize("error", [OSError("disk gone"), artifacts.ArtifactError("store gone")])
def test_an_error_of_the_store_refuses_and_writes_nothing(run, monkeypatch, error):
    artifacts.write("s", "worker", "design", content="d1")
    before = state.get_run("s", run)
    events = len(state.list_events("s"))

    def failing(*args):
        raise error

    monkeypatch.setattr(artifacts_local.LocalStore, "latest", failing)
    with pytest.raises(LadoError) as refused:
        _advance("worker", "done", note="built")
    assert "could not check the artifacts step build must write" in str(refused.value)
    assert str(error) in str(refused.value)
    _unmoved(before)
    assert len(state.list_events("s")) == events


def test_another_error_in_the_check_is_not_hidden(run, monkeypatch):
    artifacts.write("s", "worker", "design", content="d1")

    def broken(*args):
        raise ValueError("a bug")

    monkeypatch.setattr(artifacts_local.LocalStore, "latest", broken)
    with pytest.raises(ValueError, match="a bug"):
        _advance("worker", "done")


def test_the_gate_after_the_step_and_the_step_that_reads_it_show_the_artifacts(run):
    artifacts.write("s", "worker", "design", content="d1", summary="the plan")
    _advance("worker", "done", note="built")
    gate = state.open_gate("s", run)
    assert runs.gate_artifacts(gate) == "Artifacts: ship/x/design"
    assert [a.full_name for a in models.gate_info(gate).attachments] == ["ship/x/design"]
    runs.answer("s", str(gate.id), "approve")
    wrap = state.get_run("s", run)
    assert "- ship/x/design: the plan" in runs.step_text(wrap, runs.flow_of(wrap))


def test_the_step_names_its_artifacts_as_its_agent_writes_them(run):
    build = state.get_run("s", run)
    line = (
        "This step must write: {} (write_artifact); they are attached to your note when you report."
    )
    assert line.format("design") in runs.step_text(build, runs.flow_of(build))
    _to_wrap()
    wrap = state.get_run("s", run)
    assert line.format("ship/x/summary") in runs.step_text(wrap, runs.flow_of(wrap))


def test_flow_status_names_them_by_full_name(run):
    assert runs.describe(state.get_run("s", run))["produces"] == ["ship/x/design"]
    _to_wrap()
    assert runs.describe(state.get_run("s", run))["produces"] == ["ship/x/summary"]
    artifacts.write("s", "supervisor", "ship/x/summary", content="done")
    _advance("supervisor", "done")
    assert runs.describe(state.get_run("s", run))["produces"] == []
