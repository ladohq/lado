// The lead's recommendation in a gate's or a question's card (docs/design/ui.md, The
// supervisor's recommendation): the block of an open card, the closed card's quiet line, and
// which option is the primary one.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { RecommendationInfo } from "./api";
import { clock } from "./ChatText";
import { primaryOf, Recommendation, RecommendationLine } from "./Recommendation";
import { TOOLTIP_DELAY_MS } from "./Tooltip";

const AT = "2026-10-03T12:04:00.000Z";

function rec(more: Partial<RecommendationInfo> = {}): RecommendationInfo {
  return { state: "given", text: "Reject: **no** test.", choice: "reject", disagrees: false, by: "reviewer", at: AT, ...more };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const OPTIONS = ["approve", "reject"];
const label = (option: string) => option.toUpperCase();
const show = (given: RecommendationInfo | null, more: { kind?: "gate" | "question"; whole?: boolean; height?: number | null } = {}) =>
  render(<Recommendation rec={given} options={OPTIONS} label={label} kind={more.kind ?? "gate"} whole={more.whole} height={more.height} />);
const block = () => screen.getByRole("note");
const text = () => block().querySelector(".rec-text") as HTMLElement;

test("a given recommendation names its option as the card's button does, its time, and its text as Markdown", () => {
  show(rec());
  expect(block().className).toBe("rec");
  expect(block().getAttribute("aria-label")).toBe("Supervisor's recommendation");
  expect(block().querySelector(".avatar.mini")?.textContent).toBe("S");
  expect(block().querySelector(".rec-head")?.textContent).toBe(`Ssupervisor recommends REJECT${clock(AT)}`);
  expect(block().querySelector(".rec-head b")?.textContent).toBe("REJECT");
  expect(text().querySelector(".chat-body strong")?.textContent).toBe("no");
  // Nothing opens or closes it: its text scrolls in its box, which the keyboard reaches.
  expect(block().querySelector("button")).toBeNull();
  expect(text().getAttribute("tabindex")).toBe("0");
});

test.each([[null], ["maybe"]])("with the choice %s the head names only the supervisor", (choice) => {
  show(rec({ choice }));
  expect(block().querySelector(".rec-title")?.textContent).toBe("supervisor");
});

test("a gate's disagreement is a frame and a sign, its words for a screen reader and the sign's tooltip", () => {
  vi.useFakeTimers();
  try {
    show(rec({ disagrees: true }));
    expect(block().className).toBe("rec against");
    expect(block().getAttribute("aria-label")).toBe("Supervisor's recommendation, disagrees with the step's report");
    expect(block().textContent).not.toContain("disagrees");
    const sign = block().querySelector(".rec-warn") as HTMLElement;
    fireEvent.mouseEnter(sign);
    act(() => void vi.advanceTimersByTime(TOOLTIP_DELAY_MS));
    expect(screen.getByRole("tooltip").textContent).toBe("Supervisor's recommendation, disagrees with the step's report");
  } finally {
    vi.useRealTimers();
  }
});

test("a question's disagreement names the agent who asked", () => {
  show(rec({ disagrees: true, by: "developer" }), { kind: "question" });
  expect(block().getAttribute("aria-label")).toBe("Supervisor's recommendation, disagrees with developer");
});

test("a gate whose report the lead wrote itself shows no disagreement", () => {
  show(rec({ disagrees: true, by: "supervisor" }));
  expect(block().className).toBe("rec");
  expect(block().getAttribute("aria-label")).toBe("Supervisor's recommendation");
  expect(block().querySelector(".rec-warn")).toBeNull();
});

test("while it is prepared, one muted line and no block; missing or never asked, nothing", () => {
  const { container } = show(rec({ state: "asked", text: "", choice: null, at: null }));
  expect(container.textContent).toBe("Supervisor is preparing a recommendation…");
  expect(screen.queryByRole("note")).toBeNull();
  cleanup();
  expect(show(rec({ state: "missing", text: "", choice: null, at: null })).container.innerHTML).toBe("");
  cleanup();
  expect(show(null).container.innerHTML).toBe("");
});

test("its text box is as high as the splitter sets, by default the stylesheet's", () => {
  show(rec(), { height: 140 });
  expect(text().style.getPropertyValue("--adv")).toBe("140px");
  cleanup();
  show(rec());
  expect(text().style.getPropertyValue("--adv")).toBe("");
});

// jsdom lays out nothing: the text as tall as `content`, its box `box` high.
function laidOut(content: number, box: number) {
  const tall = (element: HTMLElement, value: number) => (element.classList.contains("rec-text") ? value : 0);
  vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockImplementation(function (this: HTMLElement) {
    return tall(this, content);
  });
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockImplementation(function (this: HTMLElement) {
    return tall(this, box);
  });
}

test("a text longer than its box fades at its lower edge until it is scrolled to its end", () => {
  laidOut(300, 82);
  show(rec());
  expect(text().classList.contains("has-more")).toBe(true);
  text().scrollTop = 218;
  fireEvent.scroll(text());
  expect(text().classList.contains("has-more")).toBe(false);
  text().scrollTop = 100;
  fireEvent.scroll(text());
  expect(text().classList.contains("has-more")).toBe(true);
});

// A wheel at `target`, `deltaY` down; whether something took it from the browser.
function wheel(target: Element, deltaY: number, deltaMode = 0): boolean {
  const event = new WheelEvent("wheel", { deltaY, deltaMode, bubbles: true, cancelable: true });
  target.dispatchEvent(event);
  return event.defaultPrevented;
}

test("a wheel over the whole block scrolls its text, a box a line high hard to hit; at its end the wheel goes on", () => {
  laidOut(300, 20);
  show(rec());
  const head = block().querySelector(".rec-head")!;
  expect(wheel(head, 40)).toBe(true);
  expect(text().scrollTop).toBe(40);
  expect(wheel(block(), 2, WheelEvent.DOM_DELTA_LINE)).toBe(true); // 2 lines
  expect(text().scrollTop).toBe(80);
  expect(wheel(head, -100)).toBe(true);
  expect(text().scrollTop).toBe(0);
  expect(wheel(head, -10)).toBe(false); // at its top: the page's
  expect(wheel(text(), 40)).toBe(false); // over the text the browser scrolls it
  expect(text().scrollTop).toBe(0);
  text().scrollTop = 280;
  expect(wheel(head, 40)).toBe(false); // at its end
});

test("whole, a wheel over the block is the page's", () => {
  laidOut(300, 20);
  show(rec(), { whole: true });
  expect(wheel(block().querySelector(".rec-head")!, 40)).toBe(false);
});

test("whole (Needs you, a run's page) its text never fades and is no stop of the Tab key", () => {
  laidOut(300, 82);
  show(rec(), { whole: true });
  expect(text().classList.contains("has-more")).toBe(false);
  expect(text().hasAttribute("tabindex")).toBe(false);
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
