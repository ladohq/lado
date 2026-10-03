import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, test } from "vitest";

import { fitWidth, Splitter } from "./Splitter";

const BOUNDS = { initial: 300, min: 200, max: 500 };

afterEach(cleanup);

// A column with the splitter on its `edge`; what it changes is kept as `changed`.
function Column({ edge, start = 300 }: { edge: "left" | "right"; start?: number }) {
  const [width, setWidth] = useState(start);
  return (
    <div data-testid="column" style={{ width }}>
      <Splitter label="Resize the column" edge={edge} width={width} bounds={BOUNDS} onChange={setWidth} />
    </div>
  );
}

const splitter = () => screen.getByRole("separator", { name: "Resize the column" });
const width = () => Number(splitter().getAttribute("aria-valuenow"));

test("a splitter says what it resizes, its orientation, width and bounds, and takes the focus", () => {
  render(<Column edge="right" />);
  expect(splitter().getAttribute("aria-orientation")).toBe("vertical");
  expect([width(), splitter().getAttribute("aria-valuemin"), splitter().getAttribute("aria-valuemax")]).toEqual([
    300,
    "200",
    "500",
  ]);
  expect(splitter().tabIndex).toBe(0);
});

test("the arrow keys move the edge: on a right edge, right widens", () => {
  render(<Column edge="right" />);
  fireEvent.keyDown(splitter(), { key: "ArrowRight" });
  expect(width()).toBe(340);
  fireEvent.keyDown(splitter(), { key: "ArrowLeft" });
  fireEvent.keyDown(splitter(), { key: "ArrowLeft" });
  expect(width()).toBe(260);
});

test("on a left edge, left widens", () => {
  render(<Column edge="left" />);
  fireEvent.keyDown(splitter(), { key: "ArrowLeft" });
  expect(width()).toBe(340);
});

test("dragging moves the edge with the pointer, within the bounds", () => {
  render(<Column edge="left" />);
  fireEvent.pointerDown(splitter(), { clientX: 1000 });
  fireEvent.pointerMove(window, { clientX: 950 });
  expect(width()).toBe(350);
  fireEvent.pointerMove(window, { clientX: 100 });
  expect(width()).toBe(500);
  fireEvent.pointerUp(window);
  fireEvent.pointerMove(window, { clientX: 1000 });
  expect(width()).toBe(500); // let go: the pointer moves nothing
});

test("the keys stop at the bounds", () => {
  render(<Column edge="right" start={480} />);
  fireEvent.keyDown(splitter(), { key: "ArrowRight" });
  expect(width()).toBe(500);
  for (let i = 0; i < 10; i++) fireEvent.keyDown(splitter(), { key: "ArrowLeft" });
  expect(width()).toBe(200);
});

test("a double click puts the width back to its default", () => {
  render(<Column edge="right" start={450} />);
  fireEvent.doubleClick(splitter());
  expect(width()).toBe(300);
});

test("a column is narrowed to the room there is, but never under its least width", () => {
  expect(fitWidth(400, BOUNDS, null)).toBe(400); // the room is not known yet
  expect(fitWidth(400, BOUNDS, 1000)).toBe(400);
  expect(fitWidth(400, BOUNDS, 320)).toBe(320);
  expect(fitWidth(400, BOUNDS, 120)).toBe(200);
});
