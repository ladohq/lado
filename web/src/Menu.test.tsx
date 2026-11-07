import { cleanup, fireEvent, render } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { placeBelow, useDismiss } from "./Menu";

afterEach(cleanup);

function Dismissed({ close }: { close: (event: MouseEvent) => void }) {
  const box = useRef<HTMLDivElement>(null);
  useDismiss(true, box, close);
  return <div ref={box} data-testid="box" />;
}

describe("useDismiss", () => {
  it("hands the press outside to `close`, and ignores one inside", () => {
    const close = vi.fn();
    const view = render(<Dismissed close={close} />);
    fireEvent.mouseDown(view.getByTestId("box"));
    expect(close).not.toHaveBeenCalled();
    fireEvent.mouseDown(document.body);
    expect(close).toHaveBeenCalledOnce();
    expect(close.mock.calls[0][0].target).toBe(document.body);
  });
});

// An anchor 30px wide and 30px high whose top is at 100, in a window 1000px wide.
const anchor = (left: number) => ({ left, right: left + 30, bottom: 130 });

describe("placeBelow", () => {
  it("puts a popover that fits at the anchor's left edge, 6px below it", () => {
    expect(placeBelow(anchor(100), 360, 1000)).toEqual({ position: "fixed", top: 136, left: 100, right: "auto" });
  });

  it("moves a popover that would cross the window's right edge left, 8px inside it", () => {
    expect(placeBelow(anchor(950), 360, 1000)).toEqual({ position: "fixed", top: 136, left: 632, right: "auto" });
  });

  it("keeps a popover 8px inside the window's left edge", () => {
    expect(placeBelow(anchor(2), 360, 1000)).toEqual({ position: "fixed", top: 136, left: 8, right: "auto" });
  });

  it("keeps the left margin when the popover is wider than the window", () => {
    expect(placeBelow(anchor(300), 400, 390)).toEqual({ position: "fixed", top: 136, left: 8, right: "auto" });
  });

  it("puts an `end` popover that fits at the anchor's right edge", () => {
    expect(placeBelow(anchor(600), 380, 1000, true)).toEqual({
      position: "fixed",
      top: 136,
      right: 370,
      left: "auto",
    });
  });

  it("moves an `end` popover that would cross the window's left edge right, 8px inside it", () => {
    expect(placeBelow(anchor(100), 380, 1000, true)).toEqual({
      position: "fixed",
      top: 136,
      right: 612,
      left: "auto",
    });
  });

  it("keeps an `end` popover 8px inside the window's right edge", () => {
    expect(placeBelow(anchor(975), 380, 1000, true)).toEqual({
      position: "fixed",
      top: 136,
      right: 8,
      left: "auto",
    });
  });
});
