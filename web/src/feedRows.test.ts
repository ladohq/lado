// The chat's rows: which entry continues a group, where a day divider stands.
import { expect, test } from "vitest";

import type { GateInfo, MessageInfo, RunEventInfo } from "./api";
import { feedRows, type Entry } from "./Chat";

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
    created_at: at.toISOString(),
    ...more,
  };
  return { at: at.getTime(), message: item };
}

const event = (id: number, at: Date): Entry => ({
  at: at.getTime(),
  event: { id, run: "feature/x", kind: "flow", actor: "w1", detail: "a -done-> b", created_at: at.toISOString() } as RunEventInfo,
});

const gate = (id: number, at: Date): Entry => ({ at: at.getTime(), gate: { id, created_at: at.toISOString() } as GateInfo });

// Local times on 4 Oct 2026.
const at = (hour: number, minute: number, second = 0, date = 4) => new Date(2026, 9, date, hour, minute, second);

// Each row as a word: a message's id with `+` when it continues a group, `day`, `events`, `gate`.
const shape = (list: Entry[], alone?: (one: MessageInfo) => boolean) =>
  feedRows(list, alone).map((row) =>
    "day" in row
      ? "day"
      : "events" in row
        ? `events ${row.events.length}`
        : "gate" in row
          ? "gate"
          : "answered" in row
            ? "answered"
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

test("a run event or a gate between two messages ends the group; consecutive events are one list", () => {
  const list = [
    message(1, "supervisor", "human", at(10, 0)),
    event(5, at(10, 0, 30)),
    event(6, at(10, 0, 40)),
    message(2, "supervisor", "human", at(10, 1)),
    gate(7, at(10, 1, 30)),
    message(3, "supervisor", "human", at(10, 2)),
  ];
  expect(shape(list)).toEqual(["1", "events 2", "2", "gate", "3"]);
});

test("a message that stands alone (the human's reply to a question) neither continues a group nor is continued", () => {
  const list = [
    message(1, "human", "w1", at(10, 0)),
    message(2, "human", "w1", at(10, 1), { reply_to: 9 }),
    message(3, "human", "w1", at(10, 2)),
  ];
  expect(shape(list, (one) => one.reply_to !== null)).toEqual(["1", "2", "3"]);
});

test("a divider stands between entries of different local days, and ends the group", () => {
  const list = [
    message(1, "supervisor", "human", at(23, 58, 0, 3)),
    message(2, "supervisor", "human", at(0, 1, 0, 4)),
    event(5, at(9, 0, 0, 4)),
    event(6, at(9, 0, 0, 5)),
    message(3, "supervisor", "human", at(9, 1, 0, 5)),
  ];
  expect(shape(list)).toEqual(["1", "day", "2", "events 1", "day", "events 1", "3"]);
  const days = feedRows(list).filter((row) => "day" in row);
  expect(days).toEqual([{ day: at(0, 1, 0, 4).toISOString() }, { day: at(9, 0, 0, 5).toISOString() }]);
});

test("no divider stands before the first entry", () => {
  expect(shape([message(1, "supervisor", "human", at(10, 0))])).toEqual(["1"]);
});
