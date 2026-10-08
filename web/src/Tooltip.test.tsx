import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { Tooltip, TOOLTIP_DELAY_MS } from "./Tooltip";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function show() {
  render(
    <Tooltip tip="w1 · developer · claude">
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
function placed(trigger: { left: number; top: number; width: number; height: number }) {
  const card = { width: 200, height: 40 };
  vi.stubGlobal("innerWidth", 800);
  vi.stubGlobal("innerHeight", 600);
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (
    this: HTMLElement,
  ) {
    const r = this.getAttribute("role") === "tooltip" ? { left: 0, top: 0, ...card } : trigger;
    const [right, bottom] = [r.left + r.width, r.top + r.height];
    return { ...r, x: r.left, y: r.top, right, bottom, toJSON() {} };
  });
  fireEvent.focus(show());
  return screen.getByRole("tooltip");
}

const left = (tip: HTMLElement) => parseFloat(tip.style.left);
const arrowX = (tip: HTMLElement) => parseFloat(tip.style.getPropertyValue("--arrow-x"));

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
