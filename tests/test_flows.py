import copy

import pytest
import yaml

from lado import flows

FEATURE = """\
name: feature
description: New feature, reviewed.
start: design
states:
  design:
    agent: supervisor
    do: Design it with the human.
    outcomes: {ready: design_ok}
  design_ok:
    gate: approval
    ask: Approve the design?
    outcomes: {approved: implement, rejected: design}
  implement:
    agent: developer
    do: Build it.
    outcomes: {done: review}
  review:
    agent: reviewer
    do: Review it.
    max_visits: 3
    outcomes: {approved: done, changes: implement}
  done:
    end: true
"""


def parse(data, name="feature"):
    errors: list[str] = []
    flow = flows.parse(data, name, "kit", "feature.yaml", errors)
    return flow, errors


def test_a_flow_has_work_gate_and_end_states():
    flow, errors = parse(yaml.safe_load(FEATURE))
    assert errors == []
    assert (flow.name, flow.description, flow.start, flow.kit) == (
        "feature",
        "New feature, reviewed.",
        "design",
        "kit",
    )
    review = flow.states["review"]
    assert (review.kind, review.agent, review.do, review.max_visits) == (
        flows.WORK,
        "reviewer",
        "Review it.",
        3,
    )
    assert review.outcomes == {"approved": "done", "changes": "implement"}
    gate = flow.states["design_ok"]
    assert (gate.kind, gate.gate, gate.ask) == (flows.GATE, "approval", "Approve the design?")
    assert flow.states["done"].kind == flows.END
    assert flow.roles() == {"supervisor", "developer", "reviewer"}


def _broken(change):
    data = yaml.safe_load(FEATURE)
    change(data)
    return data


@pytest.mark.parametrize(
    ("change", "error"),
    [
        (lambda d: d.update(bogus=1), "unknown keys bogus"),
        (lambda d: d.update(name="other"), 'name "other" differs from the file name "feature"'),
        (lambda d: d.pop("description"), "description is missing"),
        (lambda d: d.update(start="nowhere"), 'start "nowhere" is not a state'),
        (lambda d: d.update(states=[]), "states must map state names to states"),
        (lambda d: d["states"].update({"bad name": {"end": True}}), 'state "bad name": name'),
        (
            lambda d: d["states"]["review"].update(gate="approval"),
            'state "review": a state is exactly one of',
        ),
        (lambda d: d["states"]["review"].update(model="x"), 'state "review": unknown keys model'),
        (lambda d: d["states"]["review"].pop("do"), 'state "review": do is missing'),
        (lambda d: d["states"]["review"].update(agent=""), 'state "review": agent must be'),
        (lambda d: d["states"]["review"].update(outcomes={}), 'state "review": outcomes must'),
        (
            lambda d: d["states"]["review"]["outcomes"].update({"looks good": "done"}),
            'state "review": outcome "looks good" must be an identifier',
        ),
        (
            lambda d: d["states"]["review"]["outcomes"].update(maybe="later"),
            'state "review": outcome "maybe" goes to "later", which is not a state',
        ),
        (lambda d: d["states"]["review"].update(max_visits=0), "max_visits must be a whole"),
        (lambda d: d["states"]["review"].update(max_visits="3"), "max_visits must be a whole"),
        (lambda d: d["states"]["design_ok"].update(gate="vote"), "gate must be approval or choice"),
        (lambda d: d["states"]["design_ok"].pop("ask"), 'state "design_ok": ask is missing'),
        (
            lambda d: d["states"]["design_ok"]["outcomes"].pop("rejected"),
            'state "design_ok": an approval gate has the outcomes approved and rejected',
        ),
        (
            lambda d: d["states"]["design_ok"]["outcomes"].update(later="design"),
            'state "design_ok": an approval gate has the outcomes approved and rejected',
        ),
        (
            lambda d: d["states"]["design_ok"].update(max_visits=2),
            'state "design_ok": unknown keys max_visits',
        ),
        (
            lambda d: d["states"]["review"].update(needs=["design", "nowhere"]),
            'state "review": needs "nowhere", which is not a state',
        ),
        (
            lambda d: d["states"]["review"].update(needs="design"),
            'state "review": needs must be a list of state names',
        ),
        (
            lambda d: d["states"]["review"].update(needs=[["design"]]),
            'state "review": needs must be a list of state names',
        ),
        (
            lambda d: d["states"]["design_ok"].update(needs=["design"]),
            'state "design_ok": unknown keys needs',
        ),
        (lambda d: d["states"]["done"].update(end=False), 'state "done": end must be true'),
        (
            lambda d: d["states"]["done"].update(outcomes={"x": "design"}),
            'state "done": unknown keys outcomes',
        ),
        (
            lambda d: d["states"].update(lost={"end": True}),
            'state "lost" cannot be reached from start "design"',
        ),
        (
            lambda d: d["states"]["review"]["outcomes"].update(approved="implement"),
            "no end state can be reached from start",
        ),
    ],
)
def test_flow_errors(change, error):
    flow, errors = parse(_broken(change))
    assert flow is None
    assert any(error in e for e in errors), errors
    assert all(e.startswith("feature.yaml: ") for e in errors)


def test_a_self_loop_is_a_valid_transition():
    data = _broken(lambda d: d["states"]["review"]["outcomes"].update(again="review"))
    assert parse(data)[1] == []


def test_a_work_state_names_the_earlier_states_whose_notes_it_needs():
    data = _broken(lambda d: d["states"]["review"].update(needs=["design", "design_ok"]))
    flow, errors = parse(data)
    assert errors == []
    assert flow.states["review"].needs == ("design", "design_ok")
    assert flow.states["implement"].needs == ()


def test_a_flow_round_trips_through_its_snapshot():
    flow, _ = parse(_broken(lambda d: d["states"]["review"].update(needs=["design"])))
    snapshot = copy.deepcopy(flow.snapshot)
    again = flows.from_snapshot(snapshot, "kit")
    assert again.states == flow.states
    assert again.states["review"].needs == ("design",)
    assert again.start == flow.start


def test_a_snapshot_from_before_needs_still_works():
    # A run started by an older LADO keeps the flow as it was: no needs anywhere.
    flow = flows.from_snapshot(yaml.safe_load(FEATURE), "kit")
    assert all(state.needs == () for state in flow.states.values())
