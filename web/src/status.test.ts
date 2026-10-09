// An agent's status in the UI: no code asks for `idle` alone (`background` takes input too,
// and is shown working), and the status marks of styles.css (docs/design/ui.md).
import { expect, test } from "vitest";

import styles from "./styles.css?raw";

const sources = import.meta.glob<string>(["./**/*.{ts,tsx}", "!./**/*.test.{ts,tsx}", "!./api.gen.ts"], {
  query: "?raw",
  import: "default",
  eager: true,
});

const IDLE_COMPARED = /[!=]==?\s*["']idle["']|["']idle["']\s*[!=]==?/;

test("no source compares a status with idle: what a turn's end changes is leaving busy", () => {
  expect(Object.keys(sources).length).toBeGreaterThan(10);
  for (const [path, code] of Object.entries(sources)) {
    const line = code.split("\n").find((l) => IDLE_COMPARED.test(l));
    expect(line, `${path} compares with "idle"`).toBeUndefined();
  }
});

test("the guard finds a comparison with idle either way round", () => {
  expect(IDLE_COMPARED.test('if (agent.status === "idle") load();')).toBe(true);
  expect(IDLE_COMPARED.test("'idle' !== status")).toBe(true);
  expect(IDLE_COMPARED.test('status: "idle",')).toBe(false);
});

// The declarations of the one rule for `selector` (exactly that selector list).
function rule(selector: string, css = styles): string {
  const at = css.indexOf(`\n${selector} {`);
  expect(at, `no rule ${selector}`).toBeGreaterThanOrEqual(0);
  return css.slice(at, css.indexOf("}", at));
}

test("busy is a full green circle, background a half-filled one, idle a muted ring", () => {
  expect(rule(".dot-busy")).toContain("background: var(--done)");
  const background = rule(".dot-background");
  expect(background).toContain("border: 1.5px solid var(--done)");
  expect(background).toContain("linear-gradient(90deg, var(--done) 50%, transparent 50%)");
  expect(rule(".dot-idle")).toContain("border: 1.5px solid var(--muted)");
});

test("busy and background pulse as the session list's working dot, by one keyframes rule, and not with reduced motion", () => {
  expect(styles.match(/@keyframes activity-pulse/g)).toHaveLength(1);
  expect(styles).not.toMatch(/@keyframes \w*dot/);
  const pulse = styles.indexOf("\n.dot-busy,\n.dot-background {");
  expect(rule(".dot-busy,\n.dot-background")).toContain("animation: activity-pulse 1.6s infinite");
  // Later in the sheet than the pulse, so it wins.
  const still = "@media (prefers-reduced-motion: reduce) {\n  .dot-busy,\n  .dot-background {\n    animation: none;";
  expect(styles.indexOf(still)).toBeGreaterThan(pulse);
});
