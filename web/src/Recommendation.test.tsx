// The lead's recommendation in a gate's or a question's card (docs/design/ui.md, Flow
// gates): the open block, the closed card's quiet line, and which option is the primary one.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import type { RecommendationInfo } from "./api";
import { clock } from "./ChatText";
import { primaryOf, Recommendation, RecommendationLine } from "./Recommendation";

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
