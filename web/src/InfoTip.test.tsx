// The info button (InfoTip.tsx): opened by a press, never by hover; one open at a time; Esc
// closes it alone.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { InfoTip } from "./InfoTip";

afterEach(cleanup);

const TASK = "The team gets this as its first message and answers in the chat. You can leave it empty.";

function two() {
  render(
    <div>
      <InfoTip about="Task">{TASK}</InfoTip>
      <InfoTip about="Team">As in the last session in this folder.</InfoTip>
      <button type="button">outside</button>
    </div>,
  );
  return {
    task: screen.getByRole("button", { name: "About Task" }),
    team: screen.getByRole("button", { name: "About Team" }),
  };
}

const region = (button: HTMLElement) => document.getElementById(button.getAttribute("aria-controls")!)!;

test("a press opens it and puts the text in its status region; a press again closes it", () => {
  const { task } = two();
  expect(task.getAttribute("aria-expanded")).toBe("false");
  expect(region(task).textContent).toBe("");
  fireEvent.click(task);
  expect(task.getAttribute("aria-expanded")).toBe("true");
  expect(region(task).getAttribute("role")).toBe("status");
  expect(region(task).textContent).toBe(TASK);
  fireEvent.click(task);
  expect(region(task).textContent).toBe("");
});

test("Esc closes it, taken so the window around it stays, and the focus stays on the button", () => {
  const { task } = two();
  const parent = vi.fn((event: KeyboardEvent) => event.defaultPrevented);
  document.addEventListener("keydown", parent);
  task.focus();
  fireEvent.click(task);
  fireEvent.keyDown(task, { key: "Escape" });
  document.removeEventListener("keydown", parent);
  expect(task.getAttribute("aria-expanded")).toBe("false");
  expect(parent).toHaveReturnedWith(true);
  expect(document.activeElement).toBe(task);
});

test("a press outside closes it; opening another closes the first", () => {
  const { task, team } = two();
  fireEvent.click(task);
  fireEvent.mouseDown(screen.getByRole("button", { name: "outside" }));
  expect(task.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(task);
  fireEvent.click(team);
  expect(task.getAttribute("aria-expanded")).toBe("false");
  expect(team.getAttribute("aria-expanded")).toBe("true");
});

test("hover opens nothing, and Tab away closes it", () => {
  const { task, team } = two();
  fireEvent.mouseEnter(task);
  fireEvent.mouseOver(task);
  expect(task.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(task);
  fireEvent.blur(task, { relatedTarget: team });
  expect(task.getAttribute("aria-expanded")).toBe("false");
});
