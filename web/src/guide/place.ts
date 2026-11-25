// Where the first-run guide's card goes (docs/design/ui.md, First-run guide): one pure
// function of rectangles, so every rule is a unit test (place.test.ts); the engine only
// measures and calls it. Part of the lazy engine.
//
// A card stands beside its target, 12px from the hole (the target plus 10px) and 16px inside
// the window, centred on its anchor across: on a phone below, then above, the window's width
// less 32px; wider, the hint's `prefer` list, else right, below, above, left. Inside a window
// narrower than the screen it first tries the window's sides at the anchor's height, and a tip
// also below and above it (without pointing: its target gets the dashed pointing ring). The
// first place that fits whole, covers no part of the hole or anchor, nor what the hint keeps
// clear (its `keep`) and, for a tip, no control outside its target wins. A tip with none goes
// to the nearest free place (ringed), else onto a tall target's lower part, else beside its
// target after all; a guiding card cuts out the anchor instead and tries again, else sits at
// the window's bottom edge (the top one where only it keeps clear what the hint keeps), else
// beside its target after all. A target taller than 70% of a phone gets no dim: its anchor is
// ringed and the card sits at an edge.
import type { Side } from "./hints";

export type Rect = { x: number; y: number; w: number; h: number };

export type Placement = Rect & {
  side: Side | "edge" | "free" | "on-target";
  arrow?: { side: Side; x: number; y: number }; // on the card's edge facing the target, from its corner
  ring: "solid" | "dashed" | "none"; // the hole's ring, a tip's pointing ring, or none
  ringAnchor: boolean; // the anchor is ringed instead of the target (a target that fills a phone)
  cutAnchor: boolean; // the hole is the anchor's, not the target's
  dim: boolean;
};

export type PlaceInput = {
  card: { w: number; h: number };
  target: Rect;
  anchor?: Rect;
  dialog?: Rect; // the window the target is in, when narrower than the screen
  viewport: Rect;
  phone: boolean;
  kind: "guiding" | "tip";
  prefer?: Side[];
  obstacles: Rect[]; // what the card keeps clear of: a hint's `keep`, and for a tip the focusable elements outside its target
  inTarget?: Rect[]; // the controls inside the target (a tip on a tall target's lower part)
};

export const MARGIN = 16;
export const GAP = 12;
export const PAD = 10; // the hole around the target: the ring's line stands 8 px off it
const CORNER = 12; // the arrow from the card's corners
const STEP = 8; // the grid of the nearest free place

const grow = (r: Rect, by: number): Rect => ({ x: r.x - by, y: r.y - by, w: r.w + 2 * by, h: r.h + 2 * by });
const overlaps = (a: Rect, b: Rect) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
const clamp = (value: number, low: number, high: number) => Math.max(low, Math.min(high, value));

// The card `size` on `side` of `around`, centred on `on` across, kept inside the window.
function beside(side: Side, around: Rect, on: Rect, size: { w: number; h: number }, view: Rect): Rect {
  const cx = on.x + on.w / 2;
  const cy = on.y + on.h / 2;
  const x = clamp(cx - size.w / 2, view.x + MARGIN, view.x + view.w - MARGIN - size.w);
  const y = clamp(cy - size.h / 2, view.y + MARGIN, view.y + view.h - MARGIN - size.h);
  if (side === "right") return { x: around.x + around.w + GAP, y, ...size };
  if (side === "left") return { x: around.x - GAP - size.w, y, ...size };
  if (side === "below") return { x, y: around.y + around.h + GAP, ...size };
  return { x, y: around.y - GAP - size.h, ...size };
}

const fitsIn = (r: Rect, view: Rect) =>
  r.x >= view.x + MARGIN &&
  r.y >= view.y + MARGIN &&
  r.x + r.w <= view.x + view.w - MARGIN &&
  r.y + r.h <= view.y + view.h - MARGIN;

const FACING: Record<Side, Side> = { right: "left", left: "right", below: "above", above: "below" };

function arrowOf(side: Side, card: Rect, on: Rect): Placement["arrow"] {
  const facing = FACING[side];
  if (side === "right" || side === "left") {
    const y = clamp(on.y + on.h / 2 - card.y, CORNER, card.h - CORNER);
    return { side: facing, x: facing === "left" ? 0 : card.w, y };
  }
  const x = clamp(on.x + on.w / 2 - card.x, CORNER, card.w - CORNER);
  return { side: facing, x, y: facing === "above" ? 0 : card.h };
}

export function place(input: PlaceInput): Placement {
  const { target, anchor, dialog, viewport: view, phone, kind } = input;
  const size = phone ? { w: view.w - 2 * MARGIN, h: input.card.h } : input.card;
  const on = anchor ?? target;
  const plain = { ringAnchor: false, cutAnchor: false, dim: kind === "guiding" };
  const ring = kind === "guiding" ? "solid" : "none";
  const atEdge = (top: boolean): Rect => ({
    x: clamp(on.x + on.w / 2 - size.w / 2, view.x + MARGIN, view.x + view.w - MARGIN - size.w),
    y: top ? view.y + MARGIN : view.y + view.h - MARGIN - size.h,
    ...size,
  });
  const clear = (r: Rect) => !input.obstacles.some((one) => overlaps(r, one));
  // The bottom edge, or the top one where only it keeps clear of the obstacles.
  const edge = (): Rect => (clear(atEdge(false)) || !clear(atEdge(true)) ? atEdge(false) : atEdge(true));

  // A target that fills the phone (the login sheet): no dim, the anchor ringed, the card at an edge.
  if (phone && kind === "guiding" && target.h > 0.7 * view.h) {
    return { ...edge(), side: "edge", ring: "solid", ...plain, ringAnchor: anchor !== undefined, dim: false };
  }

  const order: Side[] = phone ? ["below", "above"] : (input.prefer ?? ["right", "below", "above", "left"]);
  const free = (r: Rect, hole: Rect, keep = true) =>
    fitsIn(r, view) && !overlaps(r, hole) && !(anchor && overlaps(r, grow(anchor, PAD))) && (!keep || clear(r));
  const sides = (hole: Rect, around: Rect, list: Side[], point: boolean, keep = true): Placement | null => {
    for (const side of list) {
      const card = beside(side, around, on, size, view);
      if (free(card, hole, keep))
        return point
          ? { ...card, side, arrow: arrowOf(side, card, on), ring, ...plain }
          : { ...card, side, ring: "dashed", ...plain };
    }
    return null;
  };

  const hole = grow(target, PAD);
  // Inside a narrower window: its sides at the anchor's height first, pointing at it.
  if (dialog && !phone && dialog.w < view.w) {
    const box = grow(dialog, PAD);
    const found =
      sides(hole, box, ["right", "left"], true) ?? (kind === "tip" ? sides(hole, box, ["below", "above"], false) : null);
    if (found) return found;
  }
  const found = sides(hole, hole, order, true);
  if (found) return found;

  if (kind === "tip") {
    const spot = nearestFree(size, target, view, input.obstacles);
    if (spot) return { ...spot, side: "free", ring: "dashed", ...plain };
    if (target.h > view.h / 2) {
      const lower = {
        x: clamp(target.x + target.w / 2 - size.w / 2, view.x + MARGIN, view.x + view.w - MARGIN - size.w),
        y: Math.min(target.y + target.h, view.y + view.h) - MARGIN - size.h,
        ...size,
      };
      if (!(input.inTarget ?? []).some((one) => overlaps(lower, one)))
        return { ...lower, side: "on-target", ring: "dashed", ...plain };
    }
    for (const side of order) {
      const card = beside(side, hole, on, size, view);
      if (fitsIn(card, view) && !overlaps(card, hole)) return { ...card, side, arrow: arrowOf(side, card, on), ring, ...plain };
    }
    return { ...edge(), side: "edge", ring: "dashed", ...plain };
  }

  // A guiding card with no place: the anchor's hole instead, then an edge; what its hint keeps
  // clear (the obstacles) is kept so first, else the card stands beside its target after all.
  const cut = (keep: boolean): Placement | null => {
    if (!anchor) return null;
    const small = grow(anchor, PAD);
    for (const side of order) {
      const card = beside(side, small, on, size, view);
      if (fitsIn(card, view) && !overlaps(card, small) && (!keep || clear(card)))
        return { ...card, side, arrow: arrowOf(side, card, on), ring, ...plain, cutAnchor: true };
    }
    return null;
  };
  const kept = cut(true) ?? (input.obstacles.length && clear(edge()) ? { ...edge(), side: "edge" as const, ring, ...plain } : null);
  return kept ?? sides(hole, hole, order, true, false) ?? cut(false) ?? { ...atEdge(false), side: "edge", ring, ...plain };
}

// The free place nearest to the target: inside the window, over neither the target nor a control.
function nearestFree(size: { w: number; h: number }, target: Rect, view: Rect, obstacles: Rect[]): Rect | null {
  const hole = grow(target, PAD);
  const cx = target.x + target.w / 2;
  const cy = target.y + target.h / 2;
  let best: Rect | null = null;
  let distance = Infinity;
  for (let y = view.y + MARGIN; y + size.h <= view.y + view.h - MARGIN; y += STEP) {
    for (let x = view.x + MARGIN; x + size.w <= view.x + view.w - MARGIN; x += STEP) {
      const card = { x, y, ...size };
      if (overlaps(card, hole) || obstacles.some((one) => overlaps(card, one))) continue;
      const far = Math.hypot(x + size.w / 2 - cx, y + size.h / 2 - cy);
      if (far < distance) {
        distance = far;
        best = card;
      }
    }
  }
  return best;
}
