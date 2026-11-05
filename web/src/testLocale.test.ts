// The locale the unit tests run in: vite.config.ts pins it, as their expected dates and orders
// are en-US's. CI's locale is en-US anyway, so the variable is checked as well as what Intl
// makes of it: without the pin the first test goes red on any machine, CI's included.
import { expect, test } from "vitest";

test("vitest's configuration sets the locale, whatever the shell's", () => {
  expect(process.env.LC_ALL).toBe("en_US.UTF-8");
});

test("the pinned locale reaches Intl", () => {
  expect(new Intl.DateTimeFormat().resolvedOptions().locale).toBe("en-US");
});
