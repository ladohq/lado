"""Flows: a kit's algorithm for one task, as states, who acts in each and allowed outcomes.

A flow is a file flows/<name>.yaml in a kit:

    name: feature                 # the file's name
    description: what it is for   # the supervisor picks a flow by it
    start: design
    states:
      design:                     # work: the agent with role `agent` does `do`
        agent: supervisor
        do: Design the change with the human.
        produces: [design]                # optional: artifacts its step must write
        outcomes: {ready: implement}      # outcome -> next state
        max_visits: 3                     # optional
      implement:
        agent: developer
        do: Build it.
        reads: [design]                   # optional: artifacts of the run it is shown
        produces: [report]
        outcomes: {done: merge_ok}
      merge_ok:                   # gate: the human answers `ask`
        gate: approval            # approval | choice
        ask: Merge it?
        reads: [design]                   # optional, as in a work state
        outcomes: {approved: done, rejected: implement}
      done:
        end: true

Artifact or note: an artifact is a step's result, a document read later (a design, a
review, a report); it is always there, so its state names it in `produces`, and no step
writes an empty one just in case. A note is the short message about the step to whoever
acts next: the verdict, the questions for the human, what changed; questions are a note,
not an artifact. What a step writes only sometimes (a mockup, a log) it attaches to its
note with flow_advance's `artifacts` when it is there; `produces` names only what is
required.

A work state's `produces` names artifacts (docs/design/artifacts.md, Flows) of the run's
scope: any outcome of the step is refused until each was written in the state's current
visit, and those records are attached to the step's note (lado.runs.advance). Gate and end
states take none.

A work or gate state's `reads` names artifacts of the run's scope too. A step is shown the
previous step's note, then one line per name with the artifact's latest record (its name,
title and summary, never its content) or that it has none yet, and on a later visit the
records of its own `produces` so far (lado.runs.step_text); a record attached to the
previous step's note is named only there. A gate shows the human the note that led to it,
then the latest record of each name it reads, except those attached to that note
(lado.runs.gate_reads). Each name of `reads` must be one some state of the flow produces
and not one of its own `produces`. That is a rule of what is used today, no invariant:
once a run has artifacts no step writes (a run's addendum, the task's context from a
tracker), `reads` takes those names as well.

An approval gate has exactly the outcomes `approved` and `rejected`; the human answers it
with approve or reject. A choice gate offers its outcome names.

A flow of LADO 0.26 or older names states in `needs`: it is refused with the way out
(NEEDS_REPLACED), and so is an open run's snapshot with it.

`parse` refuses a flow whose states cannot all be reached from start or that reaches no end.
`lint` names what a flow runs with but should not have: a state no end can be reached from
(a trap), a cycle with no state that has max_visits and no gate on it (agents could loop
forever), and a name in `reads` that no state before the reading one produces (no state
with a path to it: its step would always get "no record yet"). Only `lado kits check`
fails on them (lado.kits.lint); loading a kit, `lado kits add` and a run's snapshot do not
apply them.

This module only reads and checks the format; lado.runs runs flows. Whether each `agent`
role exists depends on the kits a session combines, so lado.kits checks that.
"""

import re
from dataclasses import dataclass, field

FLOW_KEYS = {"name", "description", "start", "states"}
WORK, GATE, END = "work", "gate", "end"
STATE_KEYS = {
    WORK: {"agent", "do", "outcomes", "max_visits", "reads", "produces"},
    GATE: {"gate", "ask", "outcomes", "reads"},
    END: {"end"},
}
GATES = ("approval", "choice")
APPROVAL = ("approved", "rejected")  # the outcomes of an approval gate, exactly these
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# An artifact's name (lado.artifacts.NAME), here so that this module stays free of LADO's.
ARTIFACT_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
# A flow of a kit (or a run's snapshot) written for LADO 0.26 or older.
NEEDS_REPLACED = (
    "needs was replaced by reads (artifact names) in LADO 0.27; name the artifacts the step reads"
)


@dataclass(frozen=True)
class State:
    name: str
    kind: str  # work, gate or end
    outcomes: dict[str, str] = field(default_factory=dict)  # outcome -> next state
    agent: str = ""  # work: the role that acts
    do: str = ""  # work: the step's instruction
    max_visits: int | None = None  # work: how often the state may be entered
    reads: tuple[str, ...] = ()  # work, gate: the run's artifacts it shows, as of now
    produces: tuple[str, ...] = ()  # work: the artifacts its step must write
    gate: str = ""  # gate: approval or choice
    ask: str = ""  # gate: the question for the human


@dataclass(frozen=True)
class Flow:
    name: str
    description: str
    start: str
    states: dict[str, State]
    snapshot: dict  # the flow as read, to rebuild it with from_snapshot
    kit: str
    path: str

    def roles(self) -> set[str]:
        return {s.agent for s in self.states.values() if s.kind == WORK}


def parse(data: object, name: str, kit: str, where: str, errors: list[str]) -> Flow | None:
    """Check a flow read from `where` and named `name` (its file name). Problems go to
    `errors`, each starting with `where`; then the result is None."""
    count = len(errors)

    def error(text: str) -> None:
        errors.append(f"{where}: {text}")

    if not isinstance(data, dict):
        error("expected a mapping")
        return None
    unknown = sorted(map(str, set(data) - FLOW_KEYS))
    if unknown:
        error(f"unknown keys {', '.join(unknown)}; allowed: {', '.join(sorted(FLOW_KEYS))}")
    if data.get("name") != name:
        error(f'name "{data.get("name")}" differs from the file name "{name}"')
    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        error("description is missing")
    raw_states = data.get("states")
    if not isinstance(raw_states, dict) or not raw_states:
        error("states must map state names to states")
        return None
    states = {}
    for state_name, raw in raw_states.items():
        state = _state(state_name, raw, error)
        if state:
            states[state.name] = state
    start = data.get("start")
    if start not in raw_states:
        error(f'start "{start}" is not a state')
    for state in states.values():
        for outcome, target in state.outcomes.items():
            if target not in raw_states:
                error(
                    f'state "{state.name}": outcome "{outcome}" goes to "{target}", '
                    "which is not a state"
                )
    produced = {artifact for state in states.values() for artifact in state.produces}
    for state in states.values():
        for read in state.reads:
            if read not in produced:
                error(f'state "{state.name}": reads "{read}", which no state of the flow produces')
    if len(errors) == count:
        _check_reachable(states, start, error)
    if len(errors) > count:
        return None
    return Flow(name, description.strip(), start, states, data, kit, where)


def from_snapshot(data: dict, kit: str) -> Flow:
    """The flow a run saved when it started."""
    errors: list[str] = []
    flow = parse(data, data.get("name"), kit, "snapshot", errors)
    if flow is None:
        raise ValueError("\n".join(errors))
    return flow


def _state(name: object, raw: object, error) -> State | None:
    if not isinstance(name, str) or not IDENTIFIER.fullmatch(name):
        error(f'state "{name}": name must be letters, digits and _, not starting with a digit')
        return None
    where = f'state "{name}"'
    if not isinstance(raw, dict):
        error(f"{where}: expected a mapping")
        return None
    kinds = [kind for kind, key in ((WORK, "agent"), (GATE, "gate"), (END, "end")) if key in raw]
    if len(kinds) != 1:
        error(f"{where}: a state is exactly one of work (agent), gate (gate) or end (end)")
        return None
    kind = kinds[0]
    if "needs" in raw:
        error(f"{where}: {NEEDS_REPLACED}")
        return None
    unknown = sorted(map(str, set(raw) - STATE_KEYS[kind]))
    if unknown:
        allowed = ", ".join(sorted(STATE_KEYS[kind]))
        error(f"{where}: unknown keys {', '.join(unknown)}; a {kind} state has: {allowed}")
        return None
    if kind == END:
        if raw["end"] is not True:
            error(f"{where}: end must be true")
            return None
        return State(name, END)
    outcomes = _outcomes(raw.get("outcomes"), where, error)
    reads = _artifact_names("reads", raw.get("reads", []), where, error)
    if reads is None:
        return None
    if kind == GATE:
        gate, ask = raw.get("gate"), raw.get("ask")
        if gate not in GATES:
            error(f"{where}: gate must be approval or choice")
        if not _text(ask):
            error(f"{where}: ask is missing")
        approval = outcomes is None or gate != "approval" or set(outcomes) == set(APPROVAL)
        if not approval:
            error(f"{where}: an approval gate has the outcomes {' and '.join(APPROVAL)}")
        if outcomes is None or gate not in GATES or not _text(ask) or not approval:
            return None
        return State(name, GATE, outcomes, reads=reads, gate=gate, ask=ask.strip())
    agent, do, visits = raw.get("agent"), raw.get("do"), raw.get("max_visits")
    ok = outcomes is not None
    if not _text(agent):
        error(f"{where}: agent must be a role name")
        ok = False
    if not _text(do):
        error(f"{where}: do is missing")
        ok = False
    if visits is not None and (type(visits) is not int or visits < 1):
        error(f"{where}: max_visits must be a whole number of 1 or more")
        ok = False
    produces = _artifact_names("produces", raw.get("produces", []), where, error)
    if not ok or produces is None:
        return None
    for own in (n for n in reads if n in produces):
        error(
            f'{where}: reads "{own}", which its own step produces; a step sees its own'
            " artifacts again by itself"
        )
        return None
    return State(
        name,
        WORK,
        outcomes,
        agent=agent,
        do=do.strip(),
        max_visits=visits,
        reads=reads,
        produces=produces,
    )


def _artifact_names(key: str, value: object, where: str, error) -> tuple[str, ...] | None:
    """The artifact names a state `reads` or a work state's step `produces`, each once."""
    if not isinstance(value, list) or not all(isinstance(n, str) for n in value):
        error(f"{where}: {key} must be a list of artifact names")
        return None
    ok = True
    for name in value:
        if not ARTIFACT_NAME.fullmatch(name):
            error(
                f'{where}: {key} "{name}" is no artifact name: 1-64 characters of a-z, 0-9,'
                ' "-", "_" and ".", starting with a letter or a digit'
            )
            ok = False
    for name in sorted({n for n in value if value.count(n) > 1}):
        error(f'{where}: {key} names "{name}" twice')
        ok = False
    return tuple(value) if ok else None


def _outcomes(value: object, where: str, error) -> dict[str, str] | None:
    if not isinstance(value, dict) or not value:
        error(f"{where}: outcomes must map outcome names to next states")
        return None
    for outcome in value:
        if not isinstance(outcome, str) or not IDENTIFIER.fullmatch(outcome):
            error(f'{where}: outcome "{outcome}" must be an identifier (letters, digits, _)')
            return None
    return {o: str(t) for o, t in value.items()}


def _check_reachable(states: dict[str, State], start: str, error) -> None:
    reached, todo = set(), [start]
    while todo:
        name = todo.pop()
        if name not in reached:
            reached.add(name)
            todo += states[name].outcomes.values()
    for name in states:
        if name not in reached:
            error(f'state "{name}" cannot be reached from start "{start}"')
    if not any(states[name].kind == END for name in reached):
        error(f'no end state can be reached from start "{start}"')


def lint(flow: Flow) -> list[str]:
    """Problems of a flow's graph that `parse` lets through (see the module's docstring),
    each starting with the flow's path, in the order of the states in the file."""
    states = flow.states
    problems = []
    to_end = {
        name for name in states if any(states[n].kind == END for n in _reached(states, [name]))
    }
    problems += [
        f'state "{name}": no end state can be reached from it'
        for name in states
        if name not in to_end
    ]
    loose = {n for n, s in states.items() if s.kind == WORK and s.max_visits is None}
    for component in _cycles(states, loose):
        cycle = " -> ".join(_cycle_path(states, component))
        problems.append(
            f"cycle {cycle} has no state with max_visits and no gate; agents could loop forever"
        )
    for name, state in states.items():
        for read in state.reads:
            # Every state is reachable from start (parse), so this asks for a state that
            # produces `read` with a path to `name` of one outcome or more.
            producers = [s for s in states.values() if read in s.produces]
            if not any(name in _reached(states, p.outcomes.values()) for p in producers):
                problems.append(f'state "{name}" reads "{read}", which no state before it produces')
    return [f"{flow.path}: {problem}" for problem in problems]


def _reached(states: dict[str, State], start, among: set[str] | None = None) -> set[str]:
    """The states reachable along outcomes from those in `start` (included), going only
    through the states `among` when given."""
    reached, todo = set(), list(start)
    while todo:
        name = todo.pop()
        if name not in reached:
            reached.add(name)
            todo += [t for t in states[name].outcomes.values() if among is None or t in among]
    return reached


def _cycles(states: dict[str, State], among: set[str]) -> list[list[str]]:
    """The strongly connected components of the states `among` that hold a cycle, each in
    file order, ordered by their first state in the file."""
    components, seen = [], set()
    for name in states:
        if name not in among or name in seen:
            continue
        ahead = _reached(states, [name], among)
        component = [n for n in states if n in ahead and name in _reached(states, [n], among)]
        seen.update(component)
        if len(component) > 1 or name in states[name].outcomes.values():
            components.append(component)
    return components


def _cycle_path(states: dict[str, State], component: list[str]) -> list[str]:
    """A cycle in `component`: from its first state, along the first outcome into the
    component, up to the first state met again; the closed part, that state twice."""
    path, name = [], component[0]
    while name not in path:
        path.append(name)
        name = next(t for t in states[name].outcomes.values() if t in component)
    return [*path[path.index(name) :], name]


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
