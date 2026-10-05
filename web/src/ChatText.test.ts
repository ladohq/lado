// Times and days as the UI writes them.
import { expect, test } from "vitest";

import { day, dayName, duration, since } from "./ChatText";

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
