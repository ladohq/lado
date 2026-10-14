import { describe, expect, it } from "vitest";

import { artifactLead, blockquote, fenced, withQuote } from "./quote";

describe("quote", () => {
  it("prefixes each line, an empty one with a bare >", () => {
    expect(blockquote("A\n\nB\n\n")).toBe("> A\n>\n> B");
    expect(blockquote("A\r\nB")).toBe("> A\n> B");
  });

  it("names the artifact and its lines", () => {
    expect(artifactLead("task/x/design", false)).toBe("In task/x/design:");
    expect(artifactLead("task/x/notes.py", false, [12, 13])).toBe("In task/x/notes.py (lines 12–13):");
    expect(artifactLead("task/x/notes.py", false, [7, 7])).toBe("In task/x/notes.py (line 7):");
    expect(artifactLead("task/x/design", true)).toBe("In task/x/design, an earlier record:");
    expect(artifactLead("task/x/notes.py", true, [1, 2])).toBe("In task/x/notes.py, an earlier record (lines 1–2):");
  });

  it("fences with more backticks than the lines hold", () => {
    expect(fenced(["  a = 1"])).toBe("```\n  a = 1\n```");
    expect(fenced(["x = '```'"])).toBe("````\nx = '```'\n````");
    expect(fenced(["a", "`````b"])).toBe("``````\na\n`````b\n``````");
  });

  it("appends after one blank line and ends on a new line", () => {
    expect(withQuote("", "> A")).toBe("> A\n");
    expect(withQuote("  \n", "> A")).toBe("> A\n");
    expect(withQuote("Почему?", "> A")).toBe("Почему?\n\n> A\n");
    expect(withQuote("Почему?\n\n\n", "> A")).toBe("Почему?\n\n> A\n");
  });
});
