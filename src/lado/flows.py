"""Flows: a kit's algorithm for one task, as states, who acts in each and allowed outcomes.

A flow is a file flows/<name>.yaml in a kit:

    name: feature                 # the file's name
    description: what it is for   # the supervisor picks a flow by it
    start: design
    states:
      design:                     # work: the agent with role `agent` does `do`
        agent: supervisor
        do: Design the change with the human.
        outcomes: {ready: design_ok}      # outcome -> next state
        max_visits: 3                     # optional
      design_ok:                  # gate: the human answers `ask`
        gate: approval            # approval | choice
        ask: Approve the design?
        outcomes: {approved: implement, rejected: design}
      implement:
        agent: developer
        do: Build it.
        needs: [design]                   # optional: states whose latest notes it gets
        outcomes: {done: done}
      done:
        end: true

A work state's step gets the previous step's note, and with `needs` also the latest note
reported from each named state (lado.runs.step_text).

An approval gate has exactly the outcomes `approved` and `rejected`; the human answers it
with approve or reject. A choice gate offers its outcome names.

This module only reads and checks the format; lado.runs runs flows. Whether each `agent`
role exists depends on the kits a session combines, so lado.kits checks that.
"""

import re
from dataclasses import dataclass, field

FLOW_KEYS = {"name", "description", "start", "states"}
WORK, GATE, END = "work", "gate", "end"
STATE_KEYS = {
    WORK: {"agent", "do", "outcomes", "max_visits", "needs"},
    GATE: {"gate", "ask", "outcomes"},
    END: {"end"},
}
GATES = ("approval", "choice")
APPROVAL = ("approved", "rejected")  # the outcomes of an approval gate, exactly these
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class State:
    name: str
    kind: str  # work, gate or end
    outcomes: dict[str, str] = field(default_factory=dict)  # outcome -> next state
    agent: str = ""  # work: the role that acts
    do: str = ""  # work: the step's instruction
    max_visits: int | None = None  # work: how often the state may be entered
    needs: tuple[str, ...] = ()  # work: the states whose latest notes the step gets
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
        for needed in state.needs:
            if needed not in raw_states:
                error(f'state "{state.name}": needs "{needed}", which is not a state')
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
        return State(name, GATE, outcomes, gate=gate, ask=ask.strip())
    agent, do, visits = raw.get("agent"), raw.get("do"), raw.get("max_visits")
    needs = raw.get("needs", [])
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
    if not isinstance(needs, list) or not all(isinstance(n, str) for n in needs):
        error(f"{where}: needs must be a list of state names")
        ok = False
    if not ok:
        return None
    return State(
        name, WORK, outcomes, agent=agent, do=do.strip(), max_visits=visits, needs=tuple(needs)
    )


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


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
