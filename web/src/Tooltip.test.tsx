import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { focusQuietly, Tooltip, TOOLTIP_DELAY_MS } from "./Tooltip";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function show(side?: "right") {
  render(
    <Tooltip tip="w1 · developer · claude" side={side}>
      <button type="button">w1</button>
    </Tooltip>,
  );
  return screen.getByRole("button", { name: "w1" });
}

test("the pointer shows the tooltip after a short delay, and leaving hides it", () => {
  const button = show();
  fireEvent.mouseEnter(button);
  act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS - 50));
  expect(screen.queryByRole("tooltip")).toBeNull();
  act(() => vi.advanceTimersByTime(50));
  const tip = screen.getByRole("tooltip");
  expect(tip.textContent).toBe("w1 · developer · claude");
  expect(button.getAttribute("aria-describedby")).toBe(tip.id);
  fireEvent.mouseLeave(button);
  expect(screen.queryByRole("tooltip")).toBeNull();
  expect(button.getAttribute("aria-describedby")).toBeNull();
});

test("`when` is asked at each entry and focus: false keeps the tooltip silent, true lets it show", () => {
  let hides = false;
  render(
    <Tooltip tip="the whole task" when={() => hides}>
      <button type="button">row</button>
    </Tooltip>,
  );
  const row = screen.getByRole("button", { name: "row" });
  fireEvent.mouseEnter(row);
  act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS));
  fireEvent.focus(row);
  expect(screen.queryByRole("tooltip")).toBeNull();
  fireEvent.blur(row);
  fireEvent.mouseLeave(row);
  hides = true;
  fireEvent.mouseEnter(row);
  act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS));
  expect(screen.getByRole("tooltip").textContent).toBe("the whole task");
  fireEvent.mouseLeave(row);
  fireEvent.focus(row);
  expect(screen.getByRole("tooltip").textContent).toBe("the whole task");
});

test("a pointer that leaves before the delay shows nothing", () => {
  const button = show();
  fireEvent.mouseEnter(button);
  fireEvent.mouseLeave(button);
  act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS * 2));
  expect(screen.queryByRole("tooltip")).toBeNull();
});

test("the focus shows it at once; Esc and leaving the focus hide it", () => {
  const button = show();
  fireEvent.focus(button);
  expect(screen.getByRole("tooltip")).toBeTruthy();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("tooltip")).toBeNull();
  fireEvent.blur(button);
  fireEvent.focus(button);
  expect(screen.getByRole("tooltip")).toBeTruthy();
  fireEvent.blur(button);
  expect(screen.queryByRole("tooltip")).toBeNull();
});

// A trigger the browser counts as :focus-visible. The answer is given here: jsdom's depends
// on the events of the tests before, and the real one is tests/ui/test_session_list.py's.
function visiblyFocusable() {
  const button = show();
  const matches = button.matches.bind(button);
  vi.spyOn(button, "matches").mockImplementation(
    (selector) => selector === ":focus-visible" || matches(selector),
  );
  return button;
}

// The tab or window leaves and comes back, as the browser sends it: a blur that leaves
// `activeElement` on the element (fireEvent.blur moves nothing), then a focus from nowhere.
function awayAndBack(element: HTMLElement) {
  fireEvent.blur(element);
  expect(document.activeElement).toBe(element);
  fireEvent.focus(element);
}

test("a focus that returns with the window to a pressed trigger shows no tooltip", () => {
  const button = visiblyFocusable();
  fireEvent.pointerDown(button);
  act(() => button.focus());
  expect(screen.queryByRole("tooltip")).toBeNull();
  awayAndBack(button);
  expect(screen.queryByRole("tooltip")).toBeNull();
});

test("a tooltip shown at the window's leaving goes, and does not come back with it", () => {
  const button = visiblyFocusable();
  act(() => button.focus());
  expect(screen.getByRole("tooltip")).toBeTruthy();
  fireEvent.blur(button);
  expect(screen.queryByRole("tooltip")).toBeNull();
  fireEvent.focus(button);
  expect(screen.queryByRole("tooltip")).toBeNull();
});

test("after the window's return the keyboard shows the tooltip: away by Tab and back", () => {
  const button = visiblyFocusable();
  act(() => button.focus());
  awayAndBack(button);
  act(() => button.blur()); // the focus really goes: Tab
  expect(screen.queryByRole("tooltip")).toBeNull();
  act(() => button.focus()); // and back: Shift+Tab
  expect(screen.getByRole("tooltip")).toBeTruthy();
});

test("after the window's return the pointer shows the tooltip after its delay", () => {
  const button = visiblyFocusable();
  act(() => button.focus());
  awayAndBack(button);
  fireEvent.mouseEnter(button);
  act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS - 50));
  expect(screen.queryByRole("tooltip")).toBeNull();
  act(() => vi.advanceTimersByTime(50));
  expect(screen.getByRole("tooltip")).toBeTruthy();
});

test("a focus moved away while the window was away does not eat the next one from an element", () => {
  const button = visiblyFocusable();
  act(() => button.focus());
  fireEvent.blur(button); // the window leaves, and comes back with the focus elsewhere
  fireEvent.focus(button, { relatedTarget: document.createElement("button") });
  expect(screen.getByRole("tooltip")).toBeTruthy();
});

// A tap on a touch screen, as the browser sends it: the pointer's down and up, then the
// mouse it emulates enters the trigger, the focus and the click.
function tap(element: HTMLElement) {
  fireEvent.pointerDown(element, { pointerType: "touch" });
  fireEvent.pointerUp(element, { pointerType: "touch" });
  fireEvent.mouseEnter(element);
  fireEvent.focus(element);
  fireEvent.click(element);
}

function hints() {
  render(
    <>
      <Tooltip tip="uiflow v1.0.0">
        <span tabIndex={0}>uiflow</span>
      </Tooltip>
      <Tooltip tip="Copy link">
        <button type="button">Copy</button>
      </Tooltip>
      <Tooltip tip="Kits page">
        <a href="/kits">Kits</a>
      </Tooltip>
      <p>elsewhere</p>
    </>,
  );
}

test("on a touch screen a tap on a hint shows its tooltip at once, and a tap elsewhere hides it", () => {
  hints();
  tap(screen.getByText("uiflow"));
  expect(screen.getByRole("tooltip").textContent).toBe("uiflow v1.0.0");
  tap(screen.getByText("uiflow")); // again: it stays
  expect(screen.getByRole("tooltip")).toBeTruthy();
  fireEvent.pointerDown(screen.getByText("elsewhere"), { pointerType: "touch" });
  expect(screen.queryByRole("tooltip")).toBeNull();
});

test("a tap on a button or a link shows no tooltip, not even after the hover's delay", () => {
  hints();
  tap(screen.getByRole("button", { name: "Copy" }));
  act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS * 2));
  expect(screen.queryByRole("tooltip")).toBeNull();
  tap(screen.getByRole("link", { name: "Kits" }));
  act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS * 2));
  expect(screen.queryByRole("tooltip")).toBeNull();
});

test("after a tap the mouse shows a tooltip on hover again", () => {
  hints();
  const button = screen.getByRole("button", { name: "Copy" });
  tap(button);
  fireEvent.mouseLeave(button); // the next tap elsewhere, or the mouse, takes the pointer away
  fireEvent.mouseEnter(button);
  act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS));
  expect(screen.getByRole("tooltip").textContent).toBe("Copy link");
});

test("the trigger keeps its own handlers, and the tooltip takes no clicks", () => {
  const clicked = vi.fn();
  render(
    <Tooltip tip="tip">
      <button type="button" onClick={clicked}>
        go
      </button>
    </Tooltip>,
  );
  const button = screen.getByRole("button", { name: "go" });
  fireEvent.focus(button);
  fireEvent.click(button);
  expect(clicked).toHaveBeenCalledOnce();
  expect(screen.getByRole("tooltip").classList.contains("tooltip")).toBe(true); // pointer-events: none
});

// A window of 800 × 600; the trigger and the card at the rectangles given (jsdom lays out nothing).
function placed(
  trigger: { left: number; top: number; width: number; height: number },
  card = { width: 200, height: 40 },
  side?: "right",
) {
  vi.stubGlobal("innerWidth", 800);
  vi.stubGlobal("innerHeight", 600);
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (
    this: HTMLElement,
  ) {
    const r = this.getAttribute("role") === "tooltip" ? { left: 0, top: 0, ...card } : trigger;
    const [right, bottom] = [r.left + r.width, r.top + r.height];
    return { ...r, x: r.left, y: r.top, right, bottom, toJSON() {} };
  });
  fireEvent.focus(show(side));
  return screen.getByRole("tooltip");
}

const left = (tip: HTMLElement) => parseFloat(tip.style.left);
const top = (tip: HTMLElement) => parseFloat(tip.style.top);
const arrowX = (tip: HTMLElement) => parseFloat(tip.style.getPropertyValue("--arrow-x"));
const arrowY = (tip: HTMLElement) => parseFloat(tip.style.getPropertyValue("--arrow-y"));

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test("under its trigger, the arrow on the top edge points at the trigger's centre", () => {
  const tip = placed({ left: 300, top: 100, width: 60, height: 20 });
  expect(tip.dataset.side).toBe("below");
  expect(parseFloat(tip.style.top)).toBeGreaterThanOrEqual(120 + 10); // room for the arrow
  expect(left(tip) + arrowX(tip)).toBe(330);
});

test("over its trigger when there is no room below, the arrow on the bottom edge", () => {
  const tip = placed({ left: 300, top: 560, width: 60, height: 20 });
  expect(tip.dataset.side).toBe("above");
  expect(parseFloat(tip.style.top) + 40).toBeLessThanOrEqual(560 - 10);
  expect(left(tip) + arrowX(tip)).toBe(330);
});

test("a narrow trigger still gets the arrow at its centre, away from the card's corner", () => {
  const tip = placed({ left: 300, top: 100, width: 16, height: 16 });
  expect(left(tip) + arrowX(tip)).toBe(308);
  expect(arrowX(tip)).toBeGreaterThanOrEqual(16);
});

test("a card pushed by the window's edge keeps its arrow at the trigger, off its ends", () => {
  let tip = placed({ left: 760, top: 100, width: 30, height: 20 });
  expect(left(tip)).toBe(800 - 8 - 200);
  expect(arrowX(tip)).toBe(775 - 592);
  cleanup();
  tip = placed({ left: 790, top: 100, width: 10, height: 20 });
  expect(arrowX(tip)).toBe(200 - 16); // past the card's end: clamped
  cleanup();
  tip = placed({ left: 0, top: 100, width: 4, height: 20 });
  expect(left(tip)).toBe(8);
  expect(arrowX(tip)).toBe(16);
});

test("a tall card goes over its trigger only when there is more room over it than under it", () => {
  const tall = { width: 200, height: 300 };
  let tip = placed({ left: 300, top: 200, width: 60, height: 20 }, tall); // 200 over, 369 under
  expect(tip.dataset.side).toBe("below");
  expect(top(tip)).toBe(231);
  cleanup();
  tip = placed({ left: 300, top: 400, width: 60, height: 20 }, tall);
  expect(tip.dataset.side).toBe("above");
  expect(top(tip)).toBe(89);
});

test("a card taller than the room on both sides stays inside the window", () => {
  const tip = placed({ left: 300, top: 200, width: 60, height: 20 }, { width: 200, height: 500 });
  expect(tip.dataset.side).toBe("below");
  expect(top(tip)).toBe(600 - 8 - 500);
});

const CARD = { width: 360, height: 214 };

test("side right: beside the trigger, level with it, the arrow on the trigger's middle", () => {
  const tip = placed({ left: 20, top: 300, width: 240, height: 50 }, CARD, "right");
  expect(tip.dataset.side).toBe("right");
  expect(left(tip)).toBe(260 + 11);
  expect(top(tip)).toBe(325 - 107);
  expect(top(tip) + arrowY(tip)).toBe(325);
});

test("side right: moved inside the window at its ends, the arrow stays at the trigger, off the corners", () => {
  let tip = placed({ left: 20, top: 540, width: 240, height: 50 }, CARD, "right");
  expect(top(tip)).toBe(600 - 8 - 214);
  expect(top(tip) + arrowY(tip)).toBe(565);
  cleanup();
  tip = placed({ left: 20, top: 0, width: 240, height: 20 }, CARD, "right");
  expect(top(tip)).toBe(8);
  expect(arrowY(tip)).toBe(16);
});

test("side right without room on the right goes under the trigger, or over it", () => {
  let tip = placed({ left: 20, top: 100, width: 500, height: 50 }, CARD, "right");
  expect(tip.dataset.side).toBe("below");
  expect(top(tip)).toBe(161);
  cleanup();
  tip = placed({ left: 20, top: 500, width: 500, height: 50 }, CARD, "right");
  expect(tip.dataset.side).toBe("above");
  expect(top(tip)).toBe(500 - 11 - 214);
});

function Silenced({ tip }: { tip: string | null }) {
  return (
    <Tooltip tip={tip}>
      <button type="button">list</button>
    </Tooltip>
  );
}

test("with no tip neither the pointer nor the focus shows anything, also after the tip comes", () => {
  const { rerender } = render(<Silenced tip={null} />);
  const button = screen.getByRole("button", { name: "list" });
  fireEvent.mouseEnter(button);
  act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS));
  fireEvent.focus(button);
  expect(screen.queryByRole("tooltip")).toBeNull();
  rerender(<Silenced tip="All 12 agents" />);
  expect(screen.queryByRole("tooltip")).toBeNull();
});

test("a tip that goes hides the tooltip that is up, and one still on its delay", () => {
  const { rerender } = render(<Silenced tip="All 12 agents" />);
  const button = screen.getByRole("button", { name: "list" });
  fireEvent.mouseEnter(button);
  act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS));
  expect(screen.getByRole("tooltip").textContent).toBe("All 12 agents");
  rerender(<Silenced tip={null} />);
  expect(screen.queryByRole("tooltip")).toBeNull();
  expect(button.getAttribute("aria-describedby")).toBeNull();
  rerender(<Silenced tip="All 12 agents" />);
  expect(screen.queryByRole("tooltip")).toBeNull(); // the pointer stayed: it asked once, for the list
  fireEvent.mouseLeave(button);
  fireEvent.mouseEnter(button);
  rerender(<Silenced tip={null} />);
  rerender(<Silenced tip="All 12 agents" />);
  act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS));
  expect(screen.queryByRole("tooltip")).toBeNull();
});

test("a focus given back quietly shows nothing, and the next focus shows as usual", () => {
  const button = visiblyFocusable();
  act(() => focusQuietly(button));
  expect(document.activeElement).toBe(button);
  expect(screen.queryByRole("tooltip")).toBeNull();
  act(() => button.blur());
  act(() => button.focus());
  expect(screen.getByRole("tooltip")).toBeTruthy();
});
