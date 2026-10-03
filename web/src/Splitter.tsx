// The edge between two columns of a page (docs/design/ui.md, Structure): drag it, or use the
// arrow keys on it, to change its column's width within the column's bounds; a double click
// puts the default width back. One component for every resizable column.
import { useEffect, useState, type RefObject } from "react";

import type { Bounds } from "./prefs";

const STEP = 40; // pixels per arrow key

const clamp = (value: number, { min, max }: Bounds) => Math.round(Math.min(max, Math.max(min, value)));

// The width a column shows: the one chosen, narrowed to the `room` there is (null: not known
// yet), but never under its least width. Only the shown width is narrowed: the chosen one
// stays remembered for a wider window.
export const fitWidth = (width: number, bounds: Bounds, room: number | null) =>
  room === null ? width : Math.max(bounds.min, Math.min(width, Math.floor(room)));

// The width of an element as it is laid out, or null before the first layout (and in jsdom,
// which lays out nothing).
export function useWidth(element: RefObject<HTMLElement | null>): number | null {
  const [width, setWidth] = useState<number | null>(null);
  useEffect(() => {
    if (typeof ResizeObserver === "undefined" || !element.current) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(element.current);
    return () => observer.disconnect();
  }, [element]);
  return width;
}

// `edge`: the side of its column the splitter is on; moving it outward widens the column.
export function Splitter({
  label,
  edge,
  width,
  bounds,
  onChange,
}: {
  label: string;
  edge: "left" | "right";
  width: number;
  bounds: Bounds;
  onChange: (width: number) => void;
}) {
  const outward = edge === "left" ? -1 : 1;
  const drag = (event: React.PointerEvent) => {
    const startX = event.clientX;
    const startWidth = width;
    const move = (moved: PointerEvent) => onChange(clamp(startWidth + outward * (moved.clientX - startX), bounds));
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
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
      onPointerDown={drag}
      onDoubleClick={() => onChange(bounds.initial)}
      onKeyDown={(event) => {
        if (event.key === "ArrowLeft") onChange(clamp(width - outward * STEP, bounds));
        if (event.key === "ArrowRight") onChange(clamp(width + outward * STEP, bounds));
      }}
    />
  );
}
