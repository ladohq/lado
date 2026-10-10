// The chips of the UI: each component has its own class names, so no rule of one styles
// another's (fix/team-chip: one global `.chip` styled the team, the kits box of New session,
// the Kits page's source filter and the attachments, and the later rules won).
import { expect, test } from "vitest";

import styles from "./styles.css?raw";

const sources = import.meta.glob<string>(["./**/*.tsx", "!./**/*.test.tsx"], {
  query: "?raw",
  import: "default",
  eager: true,
});

// Each chip class and the only files whose markup uses it.
const OWNERS: Record<string, string[]> = {
  "team-chip": ["./Team.tsx"],
  "team-chip-name": ["./Team.tsx"],
  "kits-box-chip": ["./Launch.tsx"],
  "source-chip": ["./Kits.tsx"],
  chip: ["./Attachments.tsx", "./GateCard.tsx"],
  "chip-name": ["./Attachments.tsx", "./GateCard.tsx"],
  "chip-size": ["./Attachments.tsx", "./GateCard.tsx"],
};

// The files whose className strings name `name` as a whole class.
function users(name: string): string[] {
  const used = new RegExp(`className=\\{?["\`][^"}\`]*(?<![\\w-])${name}(?![\\w-])`);
  return Object.keys(sources)
    .filter((path) => used.test(sources[path]))
    .sort();
}

test("each chip class is used by one component only", () => {
  for (const [name, owners] of Object.entries(OWNERS)) expect(users(name), name).toEqual(owners);
});

test("no chip rule is written twice in styles.css, where the later one would win", () => {
  const selectors = [...styles.matchAll(/^([^\s@}/][^{}]*)\{/gm)].map((m) => m[1].trim()).filter((s) => s.includes("chip"));
  const twice = selectors.filter((one, at) => selectors.indexOf(one) !== at);
  expect(twice).toEqual([]);
});
