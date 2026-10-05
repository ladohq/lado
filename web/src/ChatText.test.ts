// Times and days as the UI writes them.
import { expect, test } from "vitest";

import { day, dayName } from "./ChatText";

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
