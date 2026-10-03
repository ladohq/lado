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
