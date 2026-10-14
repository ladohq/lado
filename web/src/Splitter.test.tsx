import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, test, vi } from "vitest";

import { columnWidth, FakeResizeObserver } from "./fakes";
import { fitWidth, Splitter, useHeight, useWidth } from "./Splitter";

const BOUNDS = { initial: 300, min: 200, max: 500 };

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// A column with the splitter on its `edge` (a block's height for "top"); what it changes is
// kept as its width.
function Column({ edge, start = 300 }: { edge: "left" | "right" | "top"; start?: number }) {
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
  fireEvent.pointerMove(splitter(), { clientX: 950 });
  expect(width()).toBe(350);
  fireEvent.pointerMove(splitter(), { clientX: 100 });
  expect(width()).toBe(500);
  fireEvent.pointerUp(splitter());
  fireEvent.pointerMove(splitter(), { clientX: 1000 });
  expect(width()).toBe(500); // let go: the pointer moves nothing
});

// The pointer is captured by the separator, so the moves and the release come to it even
// over an iframe; jsdom has no capture, so the test sends them to it.
test("a drag captures the pointer, says it is dragging, and ends on the release or a cancel", () => {
  const captured: number[] = [];
  HTMLElement.prototype.setPointerCapture = function (id: number) {
    captured.push(id);
  };
  try {
    render(<Column edge="left" />);
    expect(splitter().dataset.dragging).toBeUndefined();
    fireEvent.pointerDown(splitter(), { clientX: 1000, pointerId: 7 });
    expect(captured).toEqual([7]);
    expect(splitter().dataset.dragging).toBe("true");
    fireEvent.pointerMove(window, { clientX: 900 });
    expect(width()).toBe(300); // not on the window: the separator has the pointer
    fireEvent.pointerCancel(splitter());
    expect(splitter().dataset.dragging).toBeUndefined();
    fireEvent.pointerMove(splitter(), { clientX: 900 });
    expect(width()).toBe(300);
  } finally {
    delete (HTMLElement.prototype as Partial<HTMLElement>).setPointerCapture;
  }
});

test("a splitter has no grip unless it asks for one", () => {
  render(<Column edge="left" />);
  expect(splitter().querySelector(".splitter-grip")).toBeNull();
  cleanup();
  render(<Splitter label="Resize the column" edge="left" width={300} bounds={BOUNDS} onChange={() => {}} grip />);
  const grip = splitter().querySelector(".splitter-grip");
  expect(grip?.getAttribute("aria-hidden")).toBe("true");
  expect(grip?.querySelectorAll(".splitter-grip-dot")).toHaveLength(3);
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

test("a splitter that resets itself calls onReset on a double click instead", () => {
  const changed = vi.fn();
  const reset = vi.fn();
  render(
    <Splitter label="Resize the column" edge="top" width={450} bounds={BOUNDS} onChange={changed} onReset={reset} />,
  );
  fireEvent.doubleClick(splitter());
  expect([changed.mock.calls, reset.mock.calls.length]).toEqual([[], 1]);
});

test("a top edge is horizontal: up makes its block taller, by the keys and by the pointer's y", () => {
  render(<Column edge="top" />);
  expect(splitter().getAttribute("aria-orientation")).toBe("horizontal");
  expect(splitter().className).toContain("splitter-top");
  expect(splitter().title).toBe("Resize the column: drag, or double-click for the default height");
  fireEvent.keyDown(splitter(), { key: "ArrowUp" });
  expect(width()).toBe(340);
  fireEvent.keyDown(splitter(), { key: "ArrowDown" });
  fireEvent.keyDown(splitter(), { key: "ArrowDown" });
  expect(width()).toBe(260);
  fireEvent.keyDown(splitter(), { key: "ArrowLeft" }); // not its keys
  fireEvent.keyDown(splitter(), { key: "ArrowRight" });
  expect(width()).toBe(260);
  fireEvent.pointerDown(splitter(), { clientX: 500, clientY: 600 });
  fireEvent.pointerMove(splitter(), { clientX: 100, clientY: 550 });
  expect(width()).toBe(310);
  fireEvent.pointerMove(splitter(), { clientX: 100, clientY: 900 });
  expect(width()).toBe(200);
  fireEvent.pointerUp(splitter());
  fireEvent.doubleClick(splitter());
  expect(width()).toBe(300);
});

test("a drag says so to onChange and calls onEnd when let go or cancelled; the keys are no drag", () => {
  const changed: [number, boolean | undefined][] = [];
  const ended = vi.fn();
  render(
    <Splitter
      label="Resize the column"
      edge="top"
      width={300}
      bounds={BOUNDS}
      onChange={(value, dragging) => changed.push([value, dragging])}
      onEnd={ended}
    />,
  );
  fireEvent.keyDown(splitter(), { key: "ArrowUp" });
  fireEvent.pointerDown(splitter(), { clientY: 600 });
  fireEvent.pointerMove(splitter(), { clientY: 590 });
  expect(ended).not.toHaveBeenCalled();
  fireEvent.pointerUp(splitter());
  fireEvent.pointerDown(splitter(), { clientY: 600 });
  fireEvent.pointerCancel(splitter());
  expect(changed).toEqual([
    [340, false],
    [310, true],
  ]);
  expect(ended).toHaveBeenCalledTimes(2);
});

test("a press on the edge selects no text and starts no drag of the browser's own", () => {
  render(<Column edge="top" />);
  expect(fireEvent.pointerDown(splitter(), { clientY: 600 })).toBe(false); // default prevented
});

test("the side edges take no up and down keys", () => {
  render(<Column edge="right" />);
  fireEvent.keyDown(splitter(), { key: "ArrowUp" });
  fireEvent.keyDown(splitter(), { key: "ArrowDown" });
  expect(width()).toBe(300);
});

// A box measured by useWidth that is drawn only once `shown`: first something else is.
function Measured({ shown }: { shown: boolean }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  if (!shown) return <p>Loading…</p>;
  return (
    <div ref={ref} data-testid="box">
      {width === null ? "not measured" : `width ${width}`}
    </div>
  );
}

test("useWidth measures an element drawn after the first render, and the one that replaces it", () => {
  columnWidth(null);
  const { rerender } = render(<Measured shown={false} />);
  rerender(<Measured shown />);
  expect(screen.getByTestId("box").textContent).toBe("not measured");
  FakeResizeObserver.resize(() => 700);
  expect(screen.getByTestId("box").textContent).toBe("width 700");
  cleanup();
  columnWidth(1000); // laid out at once, as it is observed
  render(<Measured shown />);
  expect(screen.getByTestId("box").textContent).toBe("width 1000");
});

// A box measured by useHeight.
function Tall() {
  const [ref, height] = useHeight<HTMLDivElement>();
  return (
    <div ref={ref} data-testid="box">
      {height === null ? "not measured" : `height ${height}`}
    </div>
  );
}

test("useHeight measures an element's height", () => {
  columnWidth(null);
  render(<Tall />);
  expect(screen.getByTestId("box").textContent).toBe("not measured");
  FakeResizeObserver.resize(() => 700, () => 420);
  expect(screen.getByTestId("box").textContent).toBe("height 420");
});

test("a column is narrowed to the room there is, but never under its least width", () => {
  expect(fitWidth(400, BOUNDS, null)).toBe(400); // the room is not known yet
  expect(fitWidth(400, BOUNDS, 1000)).toBe(400);
  expect(fitWidth(400, BOUNDS, 320)).toBe(320);
  expect(fitWidth(400, BOUNDS, 120)).toBe(200);
});
