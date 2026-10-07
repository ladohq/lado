"""A state's `reads`: the run's artifacts its step or its gate shows, by their latest records
(docs/design/artifacts.md, Flows)."""

import pytest
from agent_helpers import spoil_snapshot

from lado import artifacts, artifacts_local, runs, runtime, state

SHIP = """\
name: ship
description: build it, check it, the human approves, the lead wraps it up
start: build
states:
  build:
    agent: worker
    do: Build it.
    reads: [review]
    produces: [design]
    outcomes: {done: check}
  check:
    agent: worker
    do: Check it.
    reads: [design]
    produces: [review]
    max_visits: 3
    outcomes: {ok: approve, changes: build}
  approve:
    gate: approval
    ask: "Ship it?"
    reads: [design, review]
    outcomes: {approved: wrap, rejected: build}
  wrap:
    agent: supervisor
    do: Wrap it up.
    reads: [design, review]
    outcomes: {done: end}
  end: {end: true}
"""

READ_IT = "read each with read_artifact"


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


def _text():
    run = state.get_run("s", "ship/x")
    return runs.step_text(run, runs.flow_of(run))


def _build(content="the design in full", summary="first cut"):
    artifacts.write("s", "worker", "design", content=content, title="The design", summary=summary)
    _advance("worker", "done", note="built")


def _check(outcome="ok", summary="looks fine"):
    artifacts.write("s", "worker", "review", content="the review in full", summary=summary)
    _advance("worker", outcome, note="checked")


def _gate():
    return state.open_gate("s", "ship/x")


def test_a_step_names_each_artifact_it_reads_by_its_latest_record_never_its_content(run):
    _build()
    _check()
    runs.answer("s", str(_gate().id), "approve", "go")
    text = _text()
    # The lead names a run's artifacts by their full names.
    assert f"Artifacts this step reads ({READ_IT}):" in text
    assert "- ship/x/design: The design — first cut" in text
    assert "- ship/x/review: looks fine" in text
    assert "the design in full" not in text
    assert "the review in full" not in text
    # After the previous step's note.
    assert text.index("Note from the previous step: approved: go") < text.index(READ_IT)


def test_an_artifact_with_no_record_yet_is_named(run):
    text = _text()
    assert f"Artifacts this step reads ({READ_IT}):\n- review: no record yet" in text


def test_a_record_attached_to_the_previous_steps_note_is_named_only_there(run):
    _build()
    text = _text()  # check reads design, which build's note has attached
    assert "Note from the previous step: built\nArtifacts: ship/x/design" in text
    assert "- design" not in text
    assert READ_IT not in text


def test_a_newer_record_than_the_attached_one_gets_its_line(run):
    _build()
    artifacts.write("s", "worker", "design", content="v2", summary="second cut")
    text = _text()
    assert "Artifacts: ship/x/design (changed since)" in text
    assert "- design: The design — second cut" in text


def test_a_step_sees_its_own_artifacts_again_on_a_later_visit_only(run):
    artifacts.write("s", "worker", "design", content="early")
    assert "so far" not in _text()  # its first visit, with a record of design already
    _build()
    _check("changes", summary="fix the form")
    text = _text()  # build again: its design so far; check's review is on check's note
    assert "Your artifacts so far (write them again if they change):\n- design: The design" in text
    assert "Note from the previous step: checked\nArtifacts: ship/x/review" in text
    assert "- review" not in text


def test_the_gate_reads_the_names_not_attached_to_the_note_before_it(run):
    _build()
    _check()  # check's note has review attached
    gate = _gate()
    assert runs.gate_reads(gate) == ["design"]


def test_the_gate_reads_every_name_when_its_notes_artifacts_cannot_be_read(run, monkeypatch):
    _build()
    _check()

    def broken(*args):
        raise artifacts.ArtifactError("store gone")

    monkeypatch.setattr(artifacts_local.LocalStore, "record", broken)
    assert runs.gate_reads(_gate()) == ["design", "review"]


def test_a_loop_limit_reads_nothing(run):
    _build()
    for _ in range(2):
        _check("changes")
        _build()
    _check("changes")
    _build()
    gate = _gate()
    assert gate.kind == runs.LOOP
    assert runs.gate_reads(gate) == []


def test_the_gate_of_a_run_whose_flow_cannot_be_read_raises_its_problem(run):
    _build()
    _check()
    spoil_snapshot("s", "ship/x", "{not json")
    with pytest.raises(runs.SnapshotError):
        runs.gate_reads(_gate())
