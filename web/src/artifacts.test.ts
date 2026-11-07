// Artifacts in the UI: whether an attachment changed since (the one comparison of hashes) and
// how each media type is shown.
import { expect, test } from "vitest";

import { changed, GROUPS_FROM, groupByScope, KINDS, kindOf, sameHeading } from "./artifacts";
import { artifact, attachment } from "./fakes";

test("an attachment changed since when its artifact's latest record has another hash", () => {
  expect(changed(attachment(), { items: [artifact()] })).toBe("unchanged");
  expect(changed(attachment(), { items: [artifact({}, { id: "r2", hash: "h2" })] })).toBe("changed");
});

test("without the session's artifacts loaded, or without its artifact, nothing is known", () => {
  expect(changed(attachment(), null)).toBe("unknown");
  expect(changed(attachment(), undefined)).toBe("unknown");
  expect(changed(attachment(), { error: "down" })).toBe("unknown");
  expect(changed(attachment(), { items: [artifact({ id: "other" })] })).toBe("unknown");
});

test("each media type is shown as one kind", () => {
  expect(kindOf("text/markdown")).toBe("markdown");
  expect(kindOf("text/plain")).toBe("text");
  expect(kindOf("text/x-python")).toBe("text");
  expect(kindOf("application/json")).toBe("text");
  expect(kindOf("image/png")).toBe("image");
  expect(kindOf("image/svg+xml")).toBe("image");
  expect(kindOf("text/html")).toBe("html");
  expect(kindOf("application/pdf")).toBe("other");
  expect(kindOf("image/tiff")).toBe("other");
});

test("a Markdown text starts with its title when its first line is that H1, in any case", () => {
  expect(sameHeading("# The plan\n\nFirst.", "The plan")).toBe(true);
  expect(sameHeading("\n\n  \n# The plan", "The plan")).toBe(true);
  expect(sameHeading("#   the PLAN  ##\n", "  The Plan ")).toBe(true);
  expect(sameHeading("# Plan of the week\n", "The plan")).toBe(false);
  expect(sameHeading("## The plan\n", "The plan")).toBe(false);
  expect(sameHeading("#The plan\n", "The plan")).toBe(false);
  expect(sameHeading("Intro\n\n# The plan\n", "The plan")).toBe(false);
  expect(sameHeading("", "The plan")).toBe(false);
});

test("each kind has its filter's label and its row's word", () => {
  expect(KINDS.markdown).toEqual({ filter: "Documents", word: "Document" });
  expect(KINDS.text).toEqual({ filter: "Code and text", word: "Code or text" });
  expect(KINDS.image).toEqual({ filter: "Images", word: "Image" });
  expect(KINDS.html).toEqual({ filter: "HTML", word: "HTML" });
  expect(KINDS.other).toEqual({ filter: "Other", word: "File" });
});

test("artifacts go in groups by scope: Session first, then the runs in the order they came", () => {
  const one = (id: string, scope: string) => artifact({ id, scope });
  const groups = groupByScope([one("a", "run/b"), one("b", ""), one("c", "run/b"), one("d", "run/a")]);
  expect(groups.map((group) => [group.scope, group.artifacts.map((item) => item.id)])).toEqual([
    ["", ["b"]],
    ["run/b", ["a", "c"]],
    ["run/a", ["d"]],
  ]);
  expect(groupByScope([])).toEqual([]);
  expect(GROUPS_FROM).toBe(100);
});

test("with an order the groups keep it, whatever the artifacts' order", () => {
  const one = (id: string, scope: string) => artifact({ id, scope });
  const groups = groupByScope([one("a", "run/b"), one("b", ""), one("c", "run/a")], ["", "run/a", "run/b"]);
  expect(groups.map((group) => group.scope)).toEqual(["", "run/a", "run/b"]);
});
