// The chat's rows: which entry continues a group, where a day divider stands, a run's
// events in groups, the human's replies to questions; and what a flow event's line says.
import { expect, test } from "vitest";

import type { GateInfo, MessageInfo, RunEventInfo } from "./api";
import { feedRows, gateOf, goesBack, type Entry } from "./Chat";

function message(id: number, from: string, to: string, at: Date, more: Partial<MessageInfo> = {}): Entry {
  const item: MessageInfo = {
    id,
    from,
    to,
    kind: "message",
    summary: `note ${id}`,
    body: "",
    state: "delivered",
    choices: null,
    free_answer: false,
    question_state: null,
    answered_by: null,
    reply_to: null,
    choice: null,
    reply_state: null,
    attachments: [],
    created_at: at.toISOString(),
    ...more,
  };
  return { at: at.getTime(), message: item };
}

const event = (id: number, at: Date, run = "feature/x"): Entry => ({
  at: at.getTime(),
  event: { id, run, kind: "flow", actor: "w1", detail: "a -done-> b", created_at: at.toISOString() } as RunEventInfo,
});

const gate = (id: number, at: Date): Entry => ({ at: at.getTime(), gate: { id, created_at: at.toISOString() } as GateInfo });

// Local times on 4 Oct 2026.
const at = (hour: number, minute: number, second = 0, date = 4) => new Date(2026, 9, date, hour, minute, second);

// Each row as a word: a message's id with `+` when it continues a group, `day`, a run's
// group of events, `gate`, a late reply's line.
const shape = (list: Entry[]) =>
  feedRows(list).map((row) =>
    "day" in row
      ? "day"
      : "events" in row
        ? `${row.run} ${row.events.map((one) => one.id).join(",")}`
        : "gate" in row
          ? "gate"
          : "late" in row
            ? `late ${row.late.id}`
            : `${row.message.id}${row.continued ? "+" : ""}`,
  );

test("a message of the same sender to the same recipient within 5 minutes continues the group", () => {
  const list = [
    message(1, "supervisor", "human", at(10, 0)),
    message(2, "supervisor", "human", at(10, 4, 59)),
    message(3, "supervisor", "human", at(10, 9)),
  ];
  expect(shape(list)).toEqual(["1", "2+", "3+"]);
});

test("a gap of 5 minutes or more starts a new group", () => {
  const list = [message(1, "supervisor", "human", at(10, 0)), message(2, "supervisor", "human", at(10, 5))];
  expect(shape(list)).toEqual(["1", "2"]);
});

test("another sender starts a new group, as the human after an agent and an agent after the human", () => {
  const list = [
    message(1, "supervisor", "human", at(10, 0)),
    message(2, "w1", "human", at(10, 1)),
    message(3, "human", "w1", at(10, 2)),
    message(4, "w1", "human", at(10, 3)),
  ];
  expect(shape(list)).toEqual(["1", "2", "3", "4"]);
});

test("the human's messages to two agents are two groups: each says to whom", () => {
  const list = [message(1, "human", "supervisor", at(10, 0)), message(2, "human", "w1", at(10, 1))];
  expect(shape(list)).toEqual(["1", "2"]);
});

test("a question continues its agent's group", () => {
  const list = [
    message(1, "w1", "human", at(10, 0)),
    message(2, "w1", "human", at(10, 1), { kind: "question", question_state: "open" }),
  ];
  expect(shape(list)).toEqual(["1", "2+"]);
});

test("a run event or a gate between two messages ends the group; consecutive events of a run are one group", () => {
  const list = [
    message(1, "supervisor", "human", at(10, 0)),
    event(5, at(10, 0, 30)),
    event(6, at(10, 0, 40)),
    message(2, "supervisor", "human", at(10, 1)),
    gate(7, at(10, 1, 30)),
    message(3, "supervisor", "human", at(10, 2)),
  ];
  expect(shape(list)).toEqual(["1", "feature/x 5,6", "2", "gate", "3"]);
});

test("a run's events are one group until another row or another run's event comes between, however long apart", () => {
  const list = [
    event(1, at(10, 0)),
    event(2, at(13, 0)),
    event(3, at(13, 1), "fix/y"),
    event(4, at(13, 2)),
    gate(9, at(13, 3)),
    event(5, at(13, 4)),
    message(10, "supervisor", "human", at(13, 5)),
    event(6, at(13, 6)),
  ];
  expect(shape(list)).toEqual(["feature/x 1,2", "fix/y 3", "feature/x 4", "gate", "feature/x 5", "10", "feature/x 6"]);
});

// The human's replies to questions (docs/design/ui.md, Answer in the question card).
const asked = (id: number, when: Date) => message(id, "w1", "human", when, { kind: "question", question_state: "answered" });
const reply = (id: number, to: number, when: Date) => message(id, "human", "w1", when, { reply_to: to });

test("a reply right under its question is no row: the question's card shows it", () => {
  const list = [asked(1, at(10, 0)), reply(2, 1, at(10, 1)), message(3, "w1", "human", at(10, 2))];
  // Nothing stands between: the agent's next message continues the question's group.
  expect(shape(list)).toEqual(["1", "3+"]);
});

test("a reply with other rows since its question is one late line where it was given, which ends a group", () => {
  const list = [
    asked(1, at(10, 0)),
    message(3, "w1", "human", at(10, 1)),
    reply(2, 1, at(10, 2)),
    message(4, "w1", "human", at(10, 3)),
    asked(5, at(10, 4)),
    event(6, at(10, 5)),
    reply(7, 5, at(10, 6)),
  ];
  expect(shape(list)).toEqual(["1", "3+", "late 2", "4", "5+", "feature/x 6", "late 7"]);
});

test("a reply to a question not in the window is a row that neither continues a group nor is continued", () => {
  const list = [
    message(1, "human", "w1", at(10, 0)),
    reply(2, 9, at(10, 1)),
    message(3, "human", "w1", at(10, 2)),
  ];
  expect(shape(list)).toEqual(["1", "2", "3"]);
});

test("a divider stands between entries of different local days, and ends the group", () => {
  const list = [
    message(1, "supervisor", "human", at(23, 58, 0, 3)),
    message(2, "supervisor", "human", at(0, 1, 0, 4)),
    event(5, at(9, 0, 0, 4)),
    event(6, at(9, 0, 0, 5)),
    message(3, "supervisor", "human", at(9, 1, 0, 5)),
  ];
  expect(shape(list)).toEqual(["1", "day", "2", "feature/x 5", "day", "feature/x 6", "3"]);
  const days = feedRows(list).filter((row) => "day" in row);
  expect(days).toEqual([{ day: at(0, 1, 0, 4).toISOString() }, { day: at(9, 0, 0, 5).toISOString() }]);
});

test("no divider stands before the first entry", () => {
  expect(shape([message(1, "supervisor", "human", at(10, 0))])).toEqual(["1"]);
});

// A flow event's line: whether its move goes back, and the gate answer it stands for.

function moved(id: number, from: string, outcome: string, to: string, more: Partial<RunEventInfo> = {}): RunEventInfo {
  return {
    id,
    run: "feature/x",
    kind: "flow",
    actor: "w1",
    detail: `${from} -${outcome}-> ${to}`,
    transition: { from_state: from, outcome, to_state: to },
    created_at: at(10, id).toISOString(),
    ...more,
  };
}

test("a move goes back when its run left the state it enters earlier in the window, or stays in its state", () => {
  const events = [
    moved(1, "design", "ready", "architecture"),
    moved(2, "architecture", "changes", "design"),
    moved(3, "design", "ready", "architecture"),
    moved(4, "architecture", "approved", "implement"),
    moved(5, "review", "changes", "review"),
    moved(6, "build", "done", "design", { run: "fix/y" }), // another run's history
    { ...moved(7, "x", "y", "z"), kind: "flow_end", transition: null },
  ];
  expect([...goesBack(events)]).toEqual([2, 3, 5]);
});

function answered(id: number, state: string, when: Date, more: Partial<GateInfo> = {}): GateInfo {
  return {
    id,
    run: "feature/x",
    state,
    answer: "approve",
    comment: `comment ${id}`,
    answered_by: "human",
    answered_at: when.toISOString(),
    ...more,
  } as GateInfo;
}

test("the human's move is the answer to the gate of its run it left or entered, closed nearest to it", () => {
  const move = moved(1, "check", "approved", "ship", { actor: "human", created_at: at(10, 5).toISOString() });
  const gates = [
    answered(1, "check", at(9, 0)),
    answered(2, "check", at(10, 5)),
    answered(3, "check", at(10, 5), { run: "fix/y" }),
    answered(4, "check", at(10, 5), { answered_by: "supervisor" }),
    answered(5, "other", at(10, 5)),
  ];
  expect(gateOf(move, gates)?.id).toBe(2);
  // A loop limit's continue enters the gate's state: the run left another one.
  const loop = moved(2, "review", "continue", "build", { actor: "human", created_at: at(10, 7).toISOString() });
  expect(gateOf(loop, [answered(6, "build", at(10, 7)), answered(1, "check", at(10, 7))])?.id).toBe(6);
  expect(gateOf(move, [])).toBeUndefined();
  expect(gateOf({ ...move, actor: "w1" }, gates)).toBeUndefined();
});
