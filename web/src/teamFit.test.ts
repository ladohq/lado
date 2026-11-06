// The rules of the team in the head (teamFit.ts): a shortened name, an agent's mark, the
// order of the levels and where the title's limit counts.
import { expect, test } from "vitest";

import { agentMarks, chooseLevel, fitLabel, stepFits, teamSteps, type TeamStep } from "./teamFit";

const labels = (k: number, names: string[]) => names.map((name) => fitLabel(name, k, names));
const marks = (names: string[]) => names.map((name) => agentMarks(names).get(name));

test("a name is cut at its stem and keeps its number", () => {
  expect(labels(4, ["developer-2"])).toEqual(["deve…-2"]);
  expect(labels(4, ["worker_12"])).toEqual(["work…_12"]);
  expect(labels(4, ["reviewer"])).toEqual(["revi…"]);
});

test("a stem within the length leaves the name whole", () => {
  expect(labels(4, ["dev-2", "lead", "w1"])).toEqual(["dev-2", "lead", "w1"]);
  expect(labels(9, ["developer-2"])).toEqual(["developer-2"]);
});

test("names cut alike take their last word as the tail", () => {
  expect(labels(4, ["frontend-lead", "frontend-dev"])).toEqual(["fron…-lead", "fron…-dev"]);
});

test("a name not cut keeps its label beside names cut alike", () => {
  expect(labels(4, ["fron", "frontend-lead", "frontend-dev"])).toEqual(["fron", "fron…-lead", "fron…-dev"]);
});

test("labels still alike take ·2, ·3 after the later ones", () => {
  expect(labels(4, ["analyst", "analysis", "analyzer"])).toEqual(["anal…", "anal…·2", "anal…·3"]);
});

test("a mark is the first letter in capitals and the tail's number under 3 digits", () => {
  expect(marks(["supervisor", "developer-2"])).toEqual(["S", "D2"]);
  expect(marks(["worker-12"])).toEqual(["W12"]);
});

test("a number of 3 digits or more leaves its last 3 digits alone", () => {
  expect(marks(["worker-1042", "worker-100"])).toEqual(["042", "100"]);
});

test("marks alike take the first letter at which the stems part, separators left out", () => {
  expect(marks(["frontend-lead", "frontend-dev", "designer", "developer"])).toEqual(["FL", "FD", "DS", "DV"]);
  expect(marks(["tester-a", "tester-b"])).toEqual(["TA", "TB"]);
});

test("marks alike keep their number after the letters", () => {
  expect(marks(["developer-2", "designer-2"])).toEqual(["DV2", "DS2"]);
});

test("numbers alike of stems that part at once take the first letter, with no letter twice", () => {
  expect(marks(["worker-1042", "builder-1042"])).toEqual(["W042", "B042"]);
});

test("marks still alike take a digit after the later one", () => {
  expect(marks(["a-b", "ab"])).toEqual(["A", "A2"]);
  expect(marks(["abba", "abbot", "abbey"])).toEqual(["AA", "AO", "AE"]);
  expect(marks(["ab-x", "ab_x", "ac"])).toEqual(["AB", "AB2", "AC"]);
});

test("the steps go by level: whole names, names from the longest stem to 4, avatars, fewer avatars", () => {
  const steps = teamSteps(["supervisor", "dev-2", "reviewer"]);
  expect(steps).toEqual([
    { level: 0 },
    ...[10, 9, 8, 7, 6, 5, 4].map((k) => ({ level: 1, k })),
    { level: 2 },
    { level: 3, visible: 2 },
    { level: 3, visible: 1 },
    { level: 3, visible: 0 },
  ]);
});

test("short stems give level 1 one step, at 4", () => {
  expect(teamSteps(["ab", "c"]).filter((step) => step.level === 1)).toEqual([{ level: 1, k: 4 }]);
});

test("the first step that fits is chosen, and each before it was tried in order", () => {
  const steps = teamSteps(["reviewer", "dev"]);
  const tried: TeamStep[] = [];
  const chosen = chooseLevel(steps, (step) => {
    tried.push(step);
    return step.level === 2;
  });
  expect(chosen).toEqual({ level: 2 });
  expect(tried).toEqual(steps.slice(0, steps.indexOf(steps.find((step) => step.level === 2)!) + 1));
});

test("when nothing fits the last step stands", () => {
  expect(chooseLevel(teamSteps(["reviewer", "dev"]), () => false)).toEqual({ level: 3, visible: 0 });
});

test("the title's limit counts at names only", () => {
  expect(stepFits({ level: 0 }, true, false)).toBe(false);
  expect(stepFits({ level: 1, k: 4 }, true, false)).toBe(false);
  expect(stepFits({ level: 2 }, true, false)).toBe(true);
  expect(stepFits({ level: 3, visible: 1 }, true, false)).toBe(true);
});

test("a row that does not fit fails at every level", () => {
  expect(stepFits({ level: 0 }, false, true)).toBe(false);
  expect(stepFits({ level: 2 }, false, true)).toBe(false);
  expect(stepFits({ level: 3, visible: 1 }, false, true)).toBe(false);
});
