// The edge between two columns of a page (docs/design/ui.md, Structure): drag it, or use the
// arrow keys on it, to change its column's width within the column's bounds; a double click
// puts the default width back. One component for every resizable column.
import { useEffect, useRef, useState } from "react";

import type { Bounds } from "./prefs";

const STEP = 40; // pixels per arrow key

const clamp = (value: number, { min, max }: Bounds) => Math.round(Math.min(max, Math.max(min, value)));

// The width a column shows: the one chosen, narrowed to the `room` there is (null: not known
// yet), but never under its least width. Only the shown width is narrowed: the chosen one
// stays remembered for a wider window.
export const fitWidth = (width: number, bounds: Bounds, room: number | null) =>
  room === null ? width : Math.max(bounds.min, Math.min(width, Math.floor(room)));

// The width (or height) of an element as it is laid out, or null before its first layout
// (and in jsdom, which has no ResizeObserver and lays out nothing). The element is the one
// the returned ref is set on: it is observed as soon as it is drawn, however late, and again
// when another element takes its place.
function useSize<T extends HTMLElement>(side: "width" | "height"): [(element: T | null) => void, number | null] {
  const [element, setElement] = useState<T | null>(null);
  const [size, setSize] = useState<number | null>(null);
  useEffect(() => {
    if (element === null || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setSize(entry.contentRect[side]));
    observer.observe(element);
    return () => observer.disconnect();
  }, [element, side]);
  return [setElement, size];
}

export const useWidth = <T extends HTMLElement>() => useSize<T>("width");

export const useHeight = <T extends HTMLElement>() => useSize<T>("height");

// The focus of a column that collapses to a strip: after the human collapses it (`toggled`
// called before the change), the strip's button that opens it has the focus; after they open
// it, the button that collapses it. A change the human did not make with those buttons (the
// page opening, a terminal opened from a chip) leaves the focus where it is.
export function useStripFocus(collapsed: boolean) {
  const toggledHere = useRef(false);
  const open = useRef<HTMLButtonElement>(null);
  const collapse = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!toggledHere.current) return;
    toggledHere.current = false;
    (collapsed ? open : collapse).current?.focus();
  }, [collapsed]);
  const toggled = () => {
    toggledHere.current = true;
  };
  return { open, collapse, toggled };
}

// `edge`: the side of its column the splitter is on; moving it outward widens the column.
// "top" is the edge above a block (the waiting card's): horizontal, moving it up makes the
// block taller, and `width` is the block's height.
// A drag captures the pointer, so the moves and the release come to the separator also over
// an iframe; it ends on the release or when the browser cancels it. `grip`: a small handle
// drawn in the middle of the edge (the artifact panel's); the whole edge stays the handle.
// `onReset`: what a double click does instead of the default width (the waiting card goes
// back to its height by the stylesheet). `onChange` is told whether a drag moved it (true)
// or a key (false), and `onEnd` when a drag ends: the waiting card minimizes on the release
// of a drag below its least height, while the edge still holds the pointer.
export function Splitter({
  label,
  edge,
  width,
  bounds,
  onChange,
  onReset,
  onEnd,
  grip = false,
}: {
  label: string;
  edge: "left" | "right" | "top";
  width: number;
  bounds: Bounds;
  onChange: (width: number, dragging: boolean) => void;
  onReset?: () => void;
  onEnd?: () => void;
  grip?: boolean;
}) {
  const across = edge === "top";
  const outward = edge === "right" ? 1 : -1;
  const [less, more] = across
    ? ["ArrowDown", "ArrowUp"]
    : edge === "left"
      ? ["ArrowRight", "ArrowLeft"]
      : ["ArrowLeft", "ArrowRight"];
  const [dragging, setDragging] = useState(false);
  const drag = (event: React.PointerEvent<HTMLDivElement>) => {
    const separator = event.currentTarget;
    // No text selected and no drag of the browser's own: a selection a double click left
    // under the press would start one, and the browser would cancel this drag for it. That
    // also keeps the focus where it was, so the press gives it: the keys work after a click.
    event.preventDefault();
    separator.focus();
    separator.setPointerCapture?.(event.pointerId); // jsdom has none
    const at = (pointer: { clientX: number; clientY: number }) => (across ? pointer.clientY : pointer.clientX);
    const start = at(event);
    const startWidth = width;
    const move = (moved: PointerEvent) => onChange(clamp(startWidth + outward * (at(moved) - start), bounds), true);
    const end = () => {
      separator.removeEventListener("pointermove", move);
      separator.removeEventListener("pointerup", end);
      separator.removeEventListener("pointercancel", end);
      setDragging(false);
      onEnd?.();
    };
    separator.addEventListener("pointermove", move);
    separator.addEventListener("pointerup", end);
    separator.addEventListener("pointercancel", end);
    setDragging(true);
  };
  return (
    <div
      role="separator"
      aria-label={label}
      aria-orientation={across ? "horizontal" : "vertical"}
      aria-valuenow={width}
      aria-valuemin={bounds.min}
      aria-valuemax={bounds.max}
      tabIndex={0}
      title={`${label}: drag, or double-click for the default ${across ? "height" : "width"}`}
      className={`splitter splitter-${edge}`}
      data-dragging={dragging || undefined}
      onPointerDown={drag}
      onDoubleClick={() => (onReset ? onReset() : onChange(bounds.initial, false))}
      onKeyDown={(event) => {
        if (event.key === less) onChange(clamp(width - STEP, bounds), false);
        if (event.key === more) onChange(clamp(width + STEP, bounds), false);
      }}
    >
      {grip && (
        <span className="splitter-grip" aria-hidden="true">
          <span className="splitter-grip-dot" />
          <span className="splitter-grip-dot" />
          <span className="splitter-grip-dot" />
        </span>
      )}
    </div>
  );
}
