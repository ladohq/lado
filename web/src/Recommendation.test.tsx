// The lead's recommendation in a gate's or a question's card (docs/design/ui.md, Flow
// gates): the open block, the closed card's quiet line, and which option is the primary one.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import type { RecommendationInfo } from "./api";
import { clock } from "./ChatText";
import { oneLine, primaryOf, Recommendation, RecommendationBar, RecommendationLine } from "./Recommendation";

const AT = "2026-10-03T12:04:00.000Z";

function rec(more: Partial<RecommendationInfo> = {}): RecommendationInfo {
  return { state: "given", text: "Reject: **no** test.", choice: "reject", disagrees: false, by: "reviewer", at: AT, ...more };
}

afterEach(cleanup);

const block = () => screen.getByRole("region", { name: "Supervisor's recommendation" });

test("a given recommendation shows its head, its time and its whole text as Markdown", () => {
  render(<Recommendation rec={rec()} />);
  const shown = block();
  expect(shown.className).toBe("rec");
  expect(shown.querySelector(".rec-title")?.textContent).toBe("Supervisor's recommendation");
  expect(shown.querySelector(".avatar.mini")?.textContent).toBe("S");
  expect(shown.querySelector("time")?.textContent).toBe(clock(AT));
  expect(shown.querySelector(".chat-body strong")?.textContent).toBe("no");
  // The option is the blue button's to say, not the head's.
  expect(shown.querySelector(".rec-head")?.textContent).not.toContain("reject");
  expect(shown.querySelector(".rec-differs")).toBeNull();
});

test("a disagreement is an orange chip in the head and an orange band", () => {
  render(<Recommendation rec={rec({ disagrees: true })} />);
  expect(block().className).toBe("rec differs");
  expect(block().querySelector(".rec-differs")?.textContent).toBe("disagrees with reviewer");
});

test.each([
  ["asked", "Supervisor is preparing a recommendation…"],
  ["missing", "The supervisor gave no recommendation"],
] as const)("a recommendation %s is a muted line", (state, text) => {
  render(<Recommendation rec={rec({ state, text: "", choice: null, at: null })} />);
  expect(block().className).toBe("rec waiting");
  expect(block().querySelector(".rec-title")?.textContent).toBe(text);
  expect(block().querySelector(".chat-body")).toBeNull();
  expect(block().querySelector("time")).toBeNull();
});

test("none asked shows nothing", () => {
  const { container } = render(<Recommendation rec={null} />);
  expect(container.innerHTML).toBe("");
});

test("a closed card's line names the option and opens the text on a click", () => {
  render(<RecommendationLine rec={rec({ disagrees: true })} label={(option) => option.toUpperCase()} />);
  const line = screen.getByText(/Supervisor recommended: REJECT/).closest("details") as HTMLDetailsElement;
  expect(line.className).toBe("rec-closed");
  expect(line.open).toBe(false);
  expect(line.querySelector(".rec-closed-differs")?.textContent).toBe(" · disagreed with reviewer");
  fireEvent.click(line.querySelector("summary")!);
  expect(line.querySelector(".chat-body strong")?.textContent).toBe("no");
});

test("a closed card's line without an option, and none for a recommendation not given", () => {
  render(<RecommendationLine rec={rec({ choice: null })} />);
  expect(screen.getByText("Supervisor's recommendation").closest("summary")).toBeTruthy();
  cleanup();
  for (const state of ["asked", "missing"] as const) {
    const { container } = render(<RecommendationLine rec={rec({ state })} />);
    expect(container.innerHTML).toBe("");
    cleanup();
  }
});

test("the primary option is the recommended one, else the first", () => {
  const options = ["approve", "reject"];
  expect(primaryOf(options, rec())).toBe("reject");
  expect(primaryOf(options, rec({ choice: null }))).toBe("approve");
  expect(primaryOf(options, rec({ state: "asked", choice: null }))).toBe("approve");
  expect(primaryOf(options, rec({ choice: "maybe" }))).toBe("approve");
  expect(primaryOf(options, null)).toBe("approve");
});

// The waiting card's line (docs/design/ui.md, The waiting card).
const OPTIONS = ["approve", "reject"];
const label = (option: string) => option.toUpperCase();
const bar = (given: RecommendationInfo | null, more: { whole?: boolean } = {}) =>
  render(<RecommendationBar rec={given} options={OPTIONS} label={label} {...more} />);

test("the card's line names the option as its button does, then the text on one line", () => {
  bar(rec({ text: "Reject:\n\n**no** `test`, see [the log](http://x)." }));
  const line = block().querySelector("button") as HTMLButtonElement;
  expect(block().className).toBe("rec-bar");
  expect(line.querySelector(".avatar.mini")?.textContent).toBe("S");
  expect(line.querySelector(".rec-bar-name")?.textContent).toBe("Supervisor recommends REJECT:");
  expect(line.querySelector(".rec-bar-text")?.textContent).toBe("Reject: no test, see the log.");
  expect(line.getAttribute("aria-expanded")).toBe("false");
});

test("a disagreement stands right after the option, in orange, so a cut never takes it", () => {
  bar(rec({ disagrees: true }));
  expect(block().querySelector(".rec-bar-name")?.textContent).toBe("Supervisor recommends REJECT · disagrees with reviewer:");
  expect(block().querySelector(".rec-bar-name .rec-differs")?.textContent).toBe(" · disagrees with reviewer");
});

test.each([[null], ["maybe"]])("with the choice %s the line has no option of the card's", (choice) => {
  bar(rec({ choice }));
  expect(block().querySelector(".rec-bar-name")?.textContent).toBe("Supervisor's recommendation:");
});

test("a click opens the line to its text as Markdown in a box that scrolls, a second closes it", () => {
  bar(rec());
  const line = block().querySelector("button") as HTMLButtonElement;
  fireEvent.click(line);
  expect(line.getAttribute("aria-expanded")).toBe("true");
  const box = block().querySelector(".rec-bar-body") as HTMLElement;
  expect(box.getAttribute("tabindex")).toBe("0");
  expect(box.querySelector(".chat-body strong")?.textContent).toBe("no");
  expect(block().querySelector(".rec-bar-text")).toBeNull();
  fireEvent.click(line);
  expect(block().querySelector(".rec-bar-body")).toBeNull();
});

test("in the expanded card the text is whole, with nothing to open", () => {
  bar(rec(), { whole: true });
  expect(block().className).toBe("rec-bar whole");
  expect(block().querySelector("button")).toBeNull();
  expect(block().querySelector(".rec-bar-body .chat-body strong")?.textContent).toBe("no");
});

test.each([
  ["asked", "Supervisor is preparing a recommendation…"],
  ["missing", "The supervisor gave no recommendation"],
] as const)("a recommendation %s is a muted line in the card too", (state, text) => {
  bar(rec({ state, text: "", choice: null, at: null }));
  expect(block().className).toBe("rec-bar waiting");
  expect(block().textContent).toContain(text);
  expect(block().querySelector("button")).toBeNull();
});

test("none asked shows no line", () => {
  const { container } = bar(null);
  expect(container.innerHTML).toBe("");
});

test("a text on one line loses its Markdown's marks and its breaks", () => {
  expect(oneLine("# Head\n\n- **a** and _b_\n> `c` [d](http://e) ![f](g.png)")).toBe("Head a and b c d f");
});
