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

// The width of an element as it is laid out, or null before its first layout (and in jsdom,
// which has no ResizeObserver and lays out nothing). The element is the one the returned ref
// is set on: it is observed as soon as it is drawn, however late, and again when another
// element takes its place.
export function useWidth<T extends HTMLElement>(): [(element: T | null) => void, number | null] {
  const [element, setElement] = useState<T | null>(null);
  const [width, setWidth] = useState<number | null>(null);
  useEffect(() => {
    if (element === null || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(element);
    return () => observer.disconnect();
  }, [element]);
  return [setElement, width];
}

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
// A drag captures the pointer, so the moves and the release come to the separator also over
// an iframe; it ends on the release or when the browser cancels it. `grip`: a small handle
// drawn in the middle of the edge (the artifact panel's); the whole edge stays the handle.
export function Splitter({
  label,
  edge,
  width,
  bounds,
  onChange,
  grip = false,
}: {
  label: string;
  edge: "left" | "right";
  width: number;
  bounds: Bounds;
  onChange: (width: number) => void;
  grip?: boolean;
}) {
  const outward = edge === "left" ? -1 : 1;
  const [dragging, setDragging] = useState(false);
  const drag = (event: React.PointerEvent<HTMLDivElement>) => {
    const separator = event.currentTarget;
    separator.setPointerCapture?.(event.pointerId); // jsdom has none
    const startX = event.clientX;
    const startWidth = width;
    const move = (moved: PointerEvent) => onChange(clamp(startWidth + outward * (moved.clientX - startX), bounds));
    const end = () => {
      separator.removeEventListener("pointermove", move);
      separator.removeEventListener("pointerup", end);
      separator.removeEventListener("pointercancel", end);
      setDragging(false);
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
      aria-orientation="vertical"
      aria-valuenow={width}
      aria-valuemin={bounds.min}
      aria-valuemax={bounds.max}
      tabIndex={0}
      title={`${label}: drag, or double-click for the default width`}
      className={`splitter splitter-${edge}`}
      data-dragging={dragging || undefined}
      onPointerDown={drag}
      onDoubleClick={() => onChange(bounds.initial)}
      onKeyDown={(event) => {
        if (event.key === "ArrowLeft") onChange(clamp(width - outward * STEP, bounds));
        if (event.key === "ArrowRight") onChange(clamp(width + outward * STEP, bounds));
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
