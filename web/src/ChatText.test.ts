// Times and days as the UI writes them.
import { expect, test } from "vitest";

import { clamp, clock, day, dayName, duration, repeatsSummary, since } from "./ChatText";
import styles from "./styles.css?raw";

// The rules of styles.css: selector and declarations, comments left out.
const rules = () =>
  Array.from(styles.replace(/\/\*[\s\S]*?\*\//g, "").matchAll(/([^{}]+)\{([^{}]*)\}/g), ([, selector, body]) => ({
    selector: selector.trim(),
    body,
  }));

test("a message's text is 15/22 pixels and at most 720 wide only in the chat's messages", () => {
  const sized = rules().filter(({ body }) => /line-height:\s*22px|max-width:\s*720px/.test(body));
  expect(sized.length).toBeGreaterThan(0);
  for (const { selector } of sized) {
    for (const one of selector.split(",")) expect(one.trim()).toMatch(/^\.chat-message[ .]/);
  }
  // The shared text of the gate's card, Flows and an agent's task keeps its size.
  const shared = rules().find(({ selector }) => selector === ".chat-body")!;
  expect(shared.body).toMatch(/font-size:\s*14px/);
});

test("an agent's summary repeats its body when the body's first line says it, or goes on from it", () => {
  expect(repeatsSummary("merged w1", "merged w1\n\nAll checks pass.")).toBe(true);
  expect(repeatsSummary("merged w1", "\n  merged w1  \nmore")).toBe(true); // the first line not blank, trimmed
  expect(repeatsSummary("the plan for the chat…", "the plan for the chat's text, in three parts\nmore")).toBe(true);
  expect(repeatsSummary("merged w1", "All checks pass.\nmerged w1")).toBe(false);
  expect(repeatsSummary("merged w1", "merged w1 and w2")).toBe(false); // no … : the line says more
  expect(repeatsSummary("the plan…", "a plan for the chat")).toBe(false);
  expect(repeatsSummary("merged w1", "")).toBe(false);
});

const numbered = (n: number, each = "line") => Array.from({ length: n }, (_, i) => `${each} ${i + 1}`).join("\n\n");

test("a text of up to 30 lines that are not blank and 6000 characters shows whole", () => {
  expect(clamp(numbered(30), 12, 30)).toBeNull();
  expect(clamp("x".repeat(6000), 12, 30)).toBeNull();
});

test("a longer text shows its first 12 lines that are not blank, at most 2400 characters of them", () => {
  const cut = clamp(numbered(31), 12, 30)!;
  expect(cut.split("\n").filter((line) => line.trim())).toEqual(numbered(12).split("\n").filter((line) => line.trim()));
  const wide = clamp("x".repeat(6001), 12, 30)!;
  expect(wide).toBe(`${"x".repeat(2400)}…`);
  const lines = clamp(numbered(40, "y".repeat(300)), 12, 30)!;
  expect(lines.length).toBe(2401);
});

test("without a threshold of its own a text is cut at its lines, the characters from the same base", () => {
  expect(clamp(numbered(20), 20)).toBeNull();
  expect(clamp(numbered(21), 20)!.endsWith("line 20")).toBe(true);
  expect(clamp("x".repeat(601), 3)).toBe(`${"x".repeat(600)}…`);
  expect(clamp("x".repeat(600), 3)).toBeNull();
});

test("a time of day is written in 24 hours, whatever the browser's locale", () => {
  expect(clock(new Date(2026, 9, 4, 19, 53).toISOString())).toBe("19:53");
  expect(clock(new Date(2026, 9, 4, 0, 5).toISOString())).toBe("00:05");
  expect(clock("not a time")).toBe("");
});

test("a day is named by the local calendar: Today, Yesterday, else its date", () => {
  const now = new Date(2026, 9, 4, 0, 30); // just after midnight, local time
  expect(dayName(new Date(2026, 9, 4, 0, 5).toISOString(), now)).toBe("Today");
  expect(dayName(new Date(2026, 9, 3, 23, 50).toISOString(), now)).toBe("Yesterday");
  expect(dayName(new Date(2026, 9, 3, 0, 1).toISOString(), now)).toBe("Yesterday");
  const older = new Date(2026, 9, 2, 23, 59).toISOString();
  expect(dayName(older, now)).toBe(day(older));
  expect(dayName(older, now)).not.toMatch(/^$|Today|Yesterday/); // its date, in the locale's words
  // Across a month's end.
  expect(dayName(new Date(2026, 8, 30, 12).toISOString(), new Date(2026, 9, 1, 8))).toBe("Yesterday");
  expect(dayName("not a time", now)).toBe("");
});

test("a duration is said roughly, or exactly to the minute, from one rule", () => {
  const cases: [number, string, string][] = [
    [0, "<1 min", "<1 min"],
    [59, "<1 min", "<1 min"],
    [60, "1 min", "1 min"],
    [14 * 60 + 59, "14 min", "14 min"],
    [60 * 60, "1 h", "1 h"],
    [2 * 3600 + 14 * 60, "2 h", "2 h 14 min"],
    [24 * 3600 - 1, "23 h", "23 h 59 min"],
    [27 * 3600 + 20 * 60, "1 d", "1 d 3 h"],
    [48 * 3600, "2 d", "2 d"],
  ];
  for (const [seconds, rough, exact] of cases) {
    expect([duration(seconds), duration(seconds, true)]).toEqual([rough, exact]);
  }
  expect(duration(-5)).toBe("<1 min");
  expect(duration(Number.NaN, true)).toBe("<1 min");
});

test("since is the rough duration from a time to now", () => {
  const ago = (seconds: number) => new Date(Date.now() - seconds * 1000).toISOString();
  expect(since(ago(3 * 3600 + 12 * 60))).toBe(duration(3 * 3600 + 12 * 60));
  expect(since(ago(3 * 3600 + 12 * 60))).toBe("3 h");
  expect(since("not a time")).toBe("<1 min");
});
