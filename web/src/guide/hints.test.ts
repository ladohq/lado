// The guide's marker test (openspec first-run-guide, "Hints are data aimed at markers"): every
// target, anchor and kept marker of hints.ts is a data-guide marker in the UI's code, every
// condition is one the engine knows, ids are unique, texts are there and English, and every
// provider the guide has texts for is one the server knows.
import { describe, expect, it } from "vitest";

import { CONDITIONS } from "./conditions";
import { GUIDED_CLIS, HINTS, leftToShow, TIP_IDS, type Texts } from "./hints";

const sources = import.meta.glob<string>("../**/*.tsx", { query: "?raw", import: "default", eager: true });
const code = Object.entries(sources)
  .filter(([path]) => !path.includes(".test.") && !path.startsWith("../guide/"))
  .map(([, text]) => text)
  .join("\n");

// The markers the code writes: data-guide="x", a "x" in a (data-)guide={…} expression,
// data-guide={`x-${…}`} (a prefix), a name given to a prop that becomes one (guide="x"), and
// the Settings list's GUIDE_MARKERS.
const lists = [...code.matchAll(/GUIDE_MARKERS[^=]*= \{([^}]*)\}/g)].map(([, body]) => body).join("\n");
function marked(marker: string): boolean {
  if (code.includes(`data-guide="${marker}"`) || code.includes(`guide="${marker}"`)) return true;
  if (code.split("\n").some((line) => /guide=\{/.test(line) && line.includes(`"${marker}"`))) return true;
  if (lists.includes(`"${marker}"`)) return true;
  return [...code.matchAll(/data-guide=\{`([a-z-]+)\$\{/g)].some(([, prefix]) => marker.startsWith(prefix));
}

const texts = (all: Texts[]) => all.flatMap((t) => [t.title, ...t.body, t.waiting, t.done, t.link, t.note, t.help, ...(t.buttons ?? []), ...(t.links ?? []).map((l) => l.label)]);

describe("the guide's hints", () => {
  it("aim at markers that are in the UI's code", () => {
    for (const hint of HINTS) {
      for (const marker of [hint.target, hint.anchor, ...(hint.precede?.for ?? []), ...(hint.keep ?? [])]) {
        if (marker) expect(marked(marker), `${hint.id}: no element marked ${marker}`).toBe(true);
      }
    }
  });

  it("would fail for a marker the code lost", () => {
    expect(marked("model-server-add")).toBe(true);
    expect(marked("no-such-marker")).toBe(false);
    expect(marked("cli-row-claude")).toBe(true); // a template's prefix
  });

  it("name only conditions the engine knows", () => {
    for (const hint of HINTS)
      for (const [name] of hint.when)
        expect(CONDITIONS[name.replace(/^!/, "")], `${hint.id}: unknown condition ${name}`).toBeDefined();
  });

  it("have unique ids of the server's shape", () => {
    const ids = HINTS.map((hint) => hint.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) expect(id).toMatch(/^[a-z0-9-]{1,64}$/);
  });

  it("have texts, in English", () => {
    for (const hint of HINTS) {
      const all = texts([hint.texts, ...Object.values(hint.variants ?? {})]).filter((t) => t !== undefined);
      expect(hint.texts.body.length, `${hint.id} has no text`).toBeGreaterThan(0);
      for (const text of all) {
        expect(text.trim(), `${hint.id}: an empty text`).not.toBe("");
        expect(text, `${hint.id}: not English`).not.toMatch(/[Ѐ-ӿ]/);
      }
      if (hint.kind === "guiding" && !hint.centred) expect(hint.texts.waiting, `${hint.id}: no waiting line`).toBeTruthy();
    }
  });

  // That they are providers the server knows: tests/test_guide.py reads this file's `cli:`.
  it("have row texts for Claude Code and Codex CLI", () => {
    expect(GUIDED_CLIS).toEqual(["claude", "codex"]);
  });

  it("open links in a new tab to the places the human chose", () => {
    const card = HINTS.find((hint) => hint.id === "none-of-these")!;
    expect(card.texts.links!.map((l) => l.href)).toEqual([
      "https://claude.com/pricing",
      "https://chatgpt.com/pricing",
      "https://openrouter.ai/keys",
      "https://www.alibabacloud.com/help/en/model-studio/get-api-key",
    ]);
    expect(card.texts.help).toBe("Not sure what any of this means? Ask your company's IT team, or someone who knows.");
  });

  it("say what the server form shows after a refusal", () => {
    const error = HINTS.find((hint) => hint.id === "model-server-error")!;
    // An address that does not answer: nothing about a key.
    expect(error.variants!.unreachable.waiting).not.toMatch(/key/i);
    // A key refused: Check key is gone until the key changes, so the hint says it comes back.
    expect(error.texts.body.join(" ")).toMatch(/\*\*Check key\*\* comes back/);
  });

  it("say that an agent's answer is sent by its button, by the button's name", () => {
    const question = HINTS.find((hint) => hint.id === "tip-question")!;
    // The button is "Send answer to <agent>"; the tip names its start, with no ellipsis.
    expect(question.texts.body.join(" ")).toContain("then press **Send answer**.");
    expect(question.texts.body.join(" ")).not.toContain("…");
    expect(code).toContain("`Send answer to ${");
  });

  it("keep Add server in sight while saying to add a server of another kind", () => {
    const noCli = HINTS.find((hint) => hint.id === "model-no-cli")!;
    expect(noCli.keep).toContain("model-server-add");
  });

  it("list the five tips in their order", () => {
    expect(TIP_IDS).toEqual(["tip-launch", "tip-session", "tip-gate", "tip-question", "tip-terminal"]);
  });

  it("leave something to show while not completed or a tip is left with tips on", () => {
    expect(leftToShow({ completed: false, tips_off: true, shown: TIP_IDS })).toBe(true);
    expect(leftToShow({ completed: true, tips_off: false, shown: ["tip-launch"] })).toBe(true);
    expect(leftToShow({ completed: true, tips_off: true, shown: [] })).toBe(false);
    expect(leftToShow({ completed: true, tips_off: false, shown: TIP_IDS })).toBe(false);
  });
});
