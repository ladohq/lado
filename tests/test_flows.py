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
            lambda d: d["states"]["review"].update(reads=["nowhere"]),
            'state "review": reads "nowhere", which no state of the flow produces',
        ),
        (
            lambda d: d["states"]["design_ok"].update(reads=["nowhere"]),
            'state "design_ok": reads "nowhere", which no state of the flow produces',
        ),
        (
            lambda d: d["states"]["review"].update(reads="design"),
            'state "review": reads must be a list of artifact names',
        ),
        (
            lambda d: d["states"]["review"].update(reads=[["design"]]),
            'state "review": reads must be a list of artifact names',
        ),
        (
            lambda d: d["states"]["review"].update(reads=["Design"]),
            'state "review": reads "Design" is no artifact name',
        ),
        (
            lambda d: (
                _produce(d, "design", "design")
                or d["states"]["review"].update(reads=["design", "design"])
            ),
            'state "review": reads names "design" twice',
        ),
        (
            lambda d: d["states"]["review"].update(produces=["review"], reads=["review"]),
            'state "review": reads "review", which its own step produces; a step sees its own'
            " artifacts again by itself",
        ),
        (
            lambda d: (
                _produce(d, "design", "design") or d["states"]["done"].update(reads=["design"])
            ),
            'state "done": unknown keys reads',
        ),
        (
            lambda d: d["states"]["review"].update(needs=["design"]),
            'state "review": needs was replaced by reads (artifact names) in LADO 0.27; name the'
            " artifacts the step reads",
        ),
        (
            lambda d: d["states"]["design_ok"].update(needs=["design"]),
            'state "design_ok": needs was replaced by reads (artifact names) in LADO 0.27',
        ),
        (
            lambda d: d["states"]["review"].update(produces="review"),
            'state "review": produces must be a list of artifact names',
        ),
        (
            lambda d: d["states"]["review"].update(produces=[["review"]]),
            'state "review": produces must be a list of artifact names',
        ),
        (
            lambda d: d["states"]["review"].update(produces=["Review"]),
            'state "review": produces "Review" is no artifact name',
        ),
        (
            lambda d: d["states"]["review"].update(produces=["ship/review"]),
            'state "review": produces "ship/review" is no artifact name',
        ),
        (
            lambda d: d["states"]["review"].update(produces=["review", "report", "review"]),
            'state "review": produces names "review" twice',
        ),
        (
            lambda d: d["states"]["design_ok"].update(produces=["design"]),
            'state "design_ok": unknown keys produces',
        ),
        (
            lambda d: d["states"]["done"].update(produces=["design"]),
            'state "done": unknown keys produces',
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


def _produce(data, state, *names):
    data["states"][state]["produces"] = list(names)


def test_a_work_state_names_the_artifacts_its_step_reads():
    def change(d):
        _produce(d, "design", "design", "mockup.html")
        d["states"]["review"].update(reads=["mockup.html", "design"])

    flow, errors = parse(_broken(change))
    assert errors == []
    assert flow.name == "feature"
    assert flow.states["review"].reads == ("mockup.html", "design")
    assert flow.states["implement"].reads == ()
    assert "needs" not in flows.STATE_KEYS[flows.WORK] | flows.STATE_KEYS[flows.GATE]


def test_a_work_state_names_the_artifacts_its_step_must_write():
    data = _broken(lambda d: d["states"]["review"].update(produces=["review", "mockup.html"]))
    flow, errors = parse(data)
    assert errors == []
    assert flow.states["review"].produces == ("review", "mockup.html")
    assert flow.states["implement"].produces == ()
    again = flows.from_snapshot(copy.deepcopy(flow.snapshot), "kit")
    assert again.states["review"].produces == ("review", "mockup.html")


def test_a_snapshot_from_before_produces_still_works():
    flow = flows.from_snapshot(yaml.safe_load(FEATURE), "kit")
    assert all(state.produces == () for state in flow.states.values())


def test_an_artifact_name_has_one_pattern():
    from lado import artifacts

    assert artifacts.NAME is flows.ARTIFACT_NAME


def test_a_gate_names_the_artifacts_the_human_sees():
    def change(d):
        _produce(d, "design", "design")
        d["states"]["design_ok"].update(reads=["design"])

    flow, errors = parse(_broken(change))
    assert errors == []
    assert flow.states["design_ok"].reads == ("design",)


def test_a_flow_round_trips_through_its_snapshot():
    def change(d):
        _produce(d, "design", "design")
        d["states"]["review"].update(reads=["design"])
        d["states"]["design_ok"].update(reads=["design"])

    flow, _ = parse(_broken(change))
    snapshot = copy.deepcopy(flow.snapshot)
    again = flows.from_snapshot(snapshot, "kit")
    assert again.states == flow.states
    assert again.states["review"].reads == ("design",)
    assert again.states["design_ok"].reads == ("design",)
    assert again.start == flow.start


def test_a_snapshot_with_needs_cannot_be_read_and_says_why():
    # A run an older LADO started with needs: its snapshot is refused with the way out.
    data = _broken(lambda d: d["states"]["implement"].update(needs=["design"]))
    with pytest.raises(ValueError, match="needs was replaced by reads .* in LADO 0.27"):
        flows.from_snapshot(data, "kit")


# The shape of lado-dev's flows after it reads artifacts: design and review loops bounded
# by max_visits and gates, reads of artifacts written earlier.
LADO_DEV_FEATURE = """\
name: feature
description: From intent to a merged branch.
start: design
states:
  design:
    agent: supervisor
    do: Design.
    produces: [design]
    outcomes: {ready: architecture}
  architecture:
    agent: architect
    do: Review the design.
    max_visits: 3
    reads: [design]
    produces: [architecture-review]
    outcomes: {approved: design_ok, changes: design}
  design_ok:
    gate: approval
    ask: Approve?
    reads: [design]
    outcomes: {approved: implement, rejected: design}
  implement:
    agent: developer
    do: Build.
    reads: [design]
    produces: [report]
    outcomes: {done: review}
  review:
    agent: reviewer
    do: Review.
    max_visits: 3
    reads: [design, report]
    produces: [review]
    outcomes: {approved: merge_ok, changes: implement}
  merge_ok:
    gate: approval
    ask: Merge?
    outcomes: {approved: merge, rejected: implement}
  merge:
    agent: supervisor
    do: Merge.
    outcomes: {merged: done, conflict: implement, red: implement}
  done:
    end: true
"""

LADO_DEV_FIX = """\
name: fix
description: A small change.
start: implement
states:
  implement:
    agent: developer
    do: Build.
    produces: [report]
    outcomes: {done: review}
  review:
    agent: reviewer
    do: Review.
    max_visits: 3
    reads: [report]
    outcomes: {approved: merge_ok, changes: implement}
  merge_ok:
    gate: approval
    ask: Merge?
    outcomes: {approved: merge, rejected: implement}
  merge:
    agent: supervisor
    do: Merge.
    outcomes: {merged: done, conflict: implement, red: implement}
  done:
    end: true
"""


def lint(text, name="feature", change=None):
    data = yaml.safe_load(text)
    if change:
        change(data)
    flow, errors = parse(data, name)
    assert errors == []
    return flows.lint(flow)


def work(do, outcomes, **more):
    return {"agent": "developer", "do": do, "outcomes": outcomes, **more}


def test_lint_passes_flows_shaped_like_lado_dev():
    assert lint(FEATURE) == []
    assert lint(LADO_DEV_FEATURE) == []
    assert lint(LADO_DEV_FIX, "fix") == []


def test_lint_names_a_state_no_end_can_be_reached_from():
    def change(d):
        # review can go to stuck, which only loops with itself: bounded, but a trap.
        d["states"]["review"]["outcomes"]["stuck"] = "stuck"
        d["states"]["stuck"] = work("Spin.", {"again": "spin"}, max_visits=2)
        d["states"]["spin"] = work("Spin.", {"again": "stuck"})

    assert lint(FEATURE, change=change) == [
        'feature.yaml: state "stuck": no end state can be reached from it',
        'feature.yaml: state "spin": no end state can be reached from it',
    ]


def test_lint_names_a_cycle_with_no_max_visits_and_no_gate():
    def unbounded(d):
        del d["states"]["review"]["max_visits"]

    assert lint(FEATURE, change=unbounded) == [
        "feature.yaml: cycle implement -> review -> implement has no state with max_visits "
        "and no gate; agents could loop forever"
    ]

    def on_implement(d):
        unbounded(d)
        d["states"]["implement"]["max_visits"] = 5

    assert lint(FEATURE, change=on_implement) == []

    def through_a_gate(d):
        unbounded(d)
        d["states"]["review"]["outcomes"]["changes"] = "design_ok"

    assert lint(FEATURE, change=through_a_gate) == []


def test_lint_follows_the_first_outcome_into_the_cycle():
    # a -> b -> c -> b and c -> a: the text starts at a, takes the first outcome into the
    # component each time and prints the closed part.
    def change(d):
        d["start"] = "a"
        d["states"]["a"] = work("A.", {"next": "b", "out": "design"})
        d["states"]["b"] = work("B.", {"next": "c"})
        d["states"]["c"] = work("C.", {"back": "b", "restart": "a"})

    assert lint(FEATURE, change=change) == [
        "feature.yaml: cycle b -> c -> b has no state with max_visits and no gate; "
        "agents could loop forever"
    ]


def test_lint_names_an_unbounded_self_loop():
    def change(d):
        d["states"]["implement"]["outcomes"]["again"] = "implement"

    assert lint(FEATURE, change=change) == [
        "feature.yaml: cycle implement -> implement has no state with max_visits and no "
        "gate; agents could loop forever"
    ]


def test_lint_names_reads_no_state_before_the_step_produces():
    def later(d):
        _produce(d, "design", "design")
        _produce(d, "review", "review")
        d["states"]["implement"]["reads"] = ["design", "review"]
        d["states"]["design_ok"]["reads"] = ["review"]

    # review comes before implement on the review loop: it may read review's last one.
    assert lint(FEATURE, change=later) == [
        'feature.yaml: state "design_ok" reads "review", which no state before it produces'
    ]

    def off_a_loop(d):
        _produce(d, "review", "review")
        d["states"]["review"]["outcomes"] = {"approved": "done"}
        d["states"]["implement"]["reads"] = ["review"]

    assert lint(FEATURE, change=off_a_loop) == [
        'feature.yaml: state "implement" reads "review", which no state before it produces'
    ]


def test_lint_problems_do_not_stop_a_flow_from_loading_or_a_snapshot():
    data = yaml.safe_load(FEATURE)
    del data["states"]["review"]["max_visits"]
    flow, errors = parse(data)
    assert errors == []
    assert flows.lint(flows.from_snapshot(copy.deepcopy(flow.snapshot), "kit")) != []
