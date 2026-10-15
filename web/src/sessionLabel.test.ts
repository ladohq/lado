import { expect, test } from "vitest";

import type { SessionInfo } from "./api";
import { label, labelOf, titleLength } from "./sessionLabel";

const session = (name: string, title: string | null) => ({ name, title }) as SessionInfo;

test("a session is named by its title, else by its name", () => {
  expect(label(session("lado-2", "Rename sessions (LAD-66)"))).toBe("Rename sessions (LAD-66)");
  expect(label(session("lado-2", null))).toBe("lado-2");
});

test("a name alone is looked up in the live list, and stays the name when the session is not there", () => {
  const loaded = { sessions: [session("lado-2", "Review"), session("lado", null)] };
  expect(labelOf("lado-2", loaded)).toBe("Review");
  expect(labelOf("lado", loaded)).toBe("lado");
  expect(labelOf("gone", loaded)).toBe("gone");
  expect(labelOf("lado-2", null)).toBe("lado-2");
  expect(labelOf("lado-2", { error: "down" })).toBe("lado-2");
});

test("a title's length counts characters as the server does, after the trim", () => {
  expect(titleLength("  Review ")).toBe(6);
  expect(titleLength("я".repeat(80))).toBe(80);
  expect(titleLength("🚀".repeat(80))).toBe(80); // 160 UTF-16 units
});
