// A flow step's direction by the order its flow declares, and the way that runs again after
// a step back (docs/design/ui.md, Flow events).
import { expect, test } from "vitest";

import type { RunInfo } from "./api";
import { direction, runsAgain } from "./flowSteps";

type State = RunInfo["states"][number];

function flow(...states: [string, Record<string, string>][]): State[] {
  return states.map(([name, outcomes]) => ({
    name,
    kind: Object.keys(outcomes).length ? "work" : "end",
    agent: null,
    gate: null,
    ask: null,
    outcomes,
    max_visits: null,
    reads: [],
    produces: [],
  }));
}

// The sdlc kit's task flow, as far as the rule reads it.
const TASK = flow(
  ["design", { ready: "design_ok" }],
  ["design_ok", { approved: "build", rejected: "design" }],
  ["build", { ready: "review", redesign: "design" }],
  ["review", { approved: "merge_ok", changes: "build" }],
  ["merge_ok", { approved: "merge", rejected: "build" }],
  ["merge", { merged: "done", conflicts: "build" }],
  ["done", {}],
);

// A branched flow: triage takes the long way (design) or the short one (fix); review sends
// the work back to either.
const BRANCHED = flow(
  ["triage", { large: "design", small: "fix" }],
  ["design", { ready: "design_ok" }],
  ["design_ok", { approved: "build", rejected: "design" }],
  ["build", { ready: "review" }],
  ["fix", { ready: "review" }],
  ["review", { changes_build: "build", changes_fix: "fix", approved: "done" }],
  ["done", {}],
);

test("ready, changes and ready again: forward, back, forward, whatever came before", () => {
  expect(direction(TASK, "build", "review")).toBe("forward");
  expect(direction(TASK, "review", "build")).toBe("back");
  expect(direction(TASK, "build", "review")).toBe("forward");
  expect(direction(TASK, "design_ok", "design")).toBe("back");
});

test("a step that stays in its state goes back", () => {
  expect(direction(TASK, "review", "review")).toBe("back");
  expect(runsAgain(TASK, "review", "review")).toEqual(["review"]);
});

test("the way that runs again is the shortest from the state returned to to the state left", () => {
  expect(runsAgain(TASK, "review", "build")).toEqual(["build", "review"]);
  expect(runsAgain(TASK, "merge", "build")).toEqual(["build", "review", "merge_ok", "merge"]);
  expect(runsAgain(TASK, "design_ok", "design")).toEqual(["design", "design_ok"]);
});

test("in a branched flow the way is one line, through the branch returned to", () => {
  expect(direction(BRANCHED, "review", "fix")).toBe("back");
  expect(runsAgain(BRANCHED, "review", "fix")).toEqual(["fix", "review"]);
  expect(runsAgain(BRANCHED, "review", "build")).toEqual(["build", "review"]);
  expect(direction(BRANCHED, "fix", "review")).toBe("forward");
  expect(direction(BRANCHED, "build", "review")).toBe("forward");
});

test("ties go by the order the flow declares its states", () => {
  // From a to d: by b or by c, both two steps; b is declared first, though a names c first.
  const tied = flow(["a", { one: "c", two: "b" }], ["b", { go: "d" }], ["c", { go: "d" }], ["d", { back: "a" }]);
  expect(runsAgain(tied, "d", "a")).toEqual(["a", "b", "d"]);
});

test("no way from the state returned to to the state left: none", () => {
  // c sends the work back to a, but nothing leads from a to c.
  const stuck = flow(["a", { go: "b" }], ["b", {}], ["c", { back: "a" }]);
  expect(direction(stuck, "c", "a")).toBe("back");
  expect(runsAgain(stuck, "c", "a")).toBeNull();
});

test("a state not in the flow, or no flow, has no direction and no way", () => {
  expect(direction(TASK, "build", "nowhere")).toBeNull();
  expect(direction(TASK, "nowhere", "build")).toBeNull();
  expect(direction([], "build", "review")).toBeNull();
  expect(runsAgain(TASK, "review", "nowhere")).toBeNull();
  expect(runsAgain([], "review", "build")).toBeNull();
});
