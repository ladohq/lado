import { describe, expect, it } from "vitest";

import { place, type Placement, type Rect } from "./place";

const wide = { x: 0, y: 0, w: 1440, h: 900 };
const phoneView = { x: 0, y: 0, w: 390, h: 844 };
const card = { w: 320, h: 160 };
const tipCard = { w: 296, h: 120 };

const overlaps = (a: Rect, b: Rect) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
const box = (p: Placement): Rect => ({ x: p.x, y: p.y, w: p.w, h: p.h });
const inside = (a: Rect, view: Rect, margin = 16) =>
  a.x >= view.x + margin && a.y >= view.y + margin && a.x + a.w <= view.w - margin && a.y + a.h <= view.h - margin;

describe("place", () => {
  it("puts a card right of its target on a wide window, 12px away, centred on it", () => {
    const target = { x: 20, y: 400, w: 200, h: 40 };
    const p = place({ card, target, viewport: wide, phone: false, kind: "guiding", obstacles: [] });
    expect(p.side).toBe("right");
    expect(p.x).toBe(20 + 200 + 4 + 12); // the hole is the target plus 4px
    expect(p.y + p.h / 2).toBe(420);
    expect(p.ring).toBe("solid");
    expect(p.dim).toBe(true);
    expect(p.arrow).toEqual({ side: "left", x: 0, y: 80 });
  });

  it("follows a hint's prefer list first", () => {
    const target = { x: 600, y: 100, w: 300, h: 40 };
    const p = place({ card, target, viewport: wide, phone: false, kind: "tip", prefer: ["below", "right"], obstacles: [] });
    expect(p.side).toBe("below");
    expect(p.y).toBe(100 + 40 + 4 + 12);
  });

  it("goes on right, below, above, left when a side does not fit", () => {
    const target = { x: 1200, y: 750, w: 200, h: 100 }; // no room right nor below
    const p = place({ card, target, viewport: wide, phone: false, kind: "guiding", obstacles: [] });
    expect(p.side).toBe("above");
    const left = place({ card, target: { x: 1200, y: 20, w: 200, h: 860 }, viewport: wide, phone: false, kind: "guiding", obstacles: [] });
    expect(left.side).toBe("left");
  });

  it("puts a phone's card below, then above, the window's width less 32px", () => {
    const target = { x: 10, y: 10, w: 44, h: 44 };
    const p = place({ card, target, viewport: phoneView, phone: true, kind: "guiding", obstacles: [] });
    expect(p.side).toBe("below");
    expect(p.w).toBe(390 - 32);
    expect(p.x).toBe(16);
    const low = place({ card, target: { x: 10, y: 760, w: 300, h: 44 }, viewport: phoneView, phone: true, kind: "guiding", obstacles: [] });
    expect(low.side).toBe("above");
  });

  it("never covers its target or anchor, and keeps 16px from the window's edges", () => {
    for (const target of [
      { x: 0, y: 0, w: 60, h: 60 },
      { x: 1380, y: 840, w: 60, h: 60 },
      { x: 500, y: 300, w: 300, h: 200 },
    ]) {
      const p = place({ card, target, viewport: wide, phone: false, kind: "guiding", obstacles: [] });
      expect(overlaps(box(p), { x: target.x - 4, y: target.y - 4, w: target.w + 8, h: target.h + 8 })).toBe(false);
      expect(inside(box(p), wide)).toBe(true);
    }
  });

  it("inside a narrower window, beside the window at the anchor's height", () => {
    const dialog = { x: 400, y: 100, w: 640, h: 700 };
    const anchor = { x: 440, y: 500, w: 560, h: 40 };
    const p = place({ card, target: dialog, anchor, dialog, viewport: wide, phone: false, kind: "guiding", obstacles: [] });
    expect(p.side).toBe("right");
    expect(p.x).toBe(400 + 640 + 4 + 12);
    expect(p.y + p.h / 2).toBe(520);
  });

  it("puts a tip below a narrower window without an arrow, its target ringed", () => {
    const dialog = { x: 200, y: 60, w: 1040, h: 600 }; // no room beside it
    const target = { x: 240, y: 200, w: 960, h: 80 };
    const p = place({ card: tipCard, target, dialog, viewport: wide, phone: false, kind: "tip", obstacles: [dialog] });
    expect(p.side).toBe("below");
    expect(p.y).toBeGreaterThanOrEqual(660 + 12);
    expect(p.arrow).toBeUndefined();
    expect(p.ring).toBe("dashed");
  });

  it("keeps a tip off the controls outside its target", () => {
    const target = { x: 20, y: 400, w: 200, h: 40 };
    const control = { x: 240, y: 380, w: 300, h: 120 }; // right of the target
    const p = place({ card: tipCard, target, viewport: wide, phone: false, kind: "tip", obstacles: [control] });
    expect(p.side).not.toBe("right");
    expect(overlaps(box(p), control)).toBe(false);
  });

  it("puts a tip with no side in the nearest free place, ringed dashed", () => {
    const target = { x: 500, y: 300, w: 200, h: 40 };
    const around = [
      { x: 0, y: 0, w: 1440, h: 290 },
      { x: 0, y: 350, w: 1440, h: 300 },
      { x: 0, y: 290, w: 490, h: 60 },
      { x: 710, y: 290, w: 730, h: 60 },
    ];
    const p = place({ card: tipCard, target, viewport: wide, phone: false, kind: "tip", obstacles: around });
    expect(p.side).toBe("free");
    expect(p.arrow).toBeUndefined();
    expect(p.ring).toBe("dashed");
    for (const one of around) expect(overlaps(box(p), one)).toBe(false);
    expect(overlaps(box(p), target)).toBe(false);
  });

  it("puts a tip on the lower part of a tall target when nothing else is free", () => {
    const target = { x: 0, y: 0, w: 1440, h: 900 }; // a full-screen terminal
    const bar = { x: 0, y: 0, w: 1440, h: 40 }; // its own bar, a control of the target
    const p = place({ card: tipCard, target, viewport: wide, phone: false, kind: "tip", obstacles: [], inTarget: [bar] });
    expect(p.side).toBe("on-target");
    expect(p.y + p.h).toBeLessThanOrEqual(900 - 16);
    expect(overlaps(box(p), bar)).toBe(false);
  });

  it("puts a tip beside its target after all, over controls, when nothing is free", () => {
    const target = { x: 500, y: 300, w: 200, h: 40 };
    const all = [{ x: 0, y: 0, w: 1440, h: 900 }];
    const p = place({ card: tipCard, target, viewport: wide, phone: false, kind: "tip", obstacles: all });
    expect(p.side).toBe("right");
    expect(p.arrow).toBeDefined();
  });

  it("cuts out the anchor instead of the target when a guiding card has no place", () => {
    const target = { x: 300, y: 60, w: 840, h: 780 }; // a big form
    const anchor = { x: 320, y: 700, w: 400, h: 40 };
    const p = place({ card, target, anchor, viewport: wide, phone: false, kind: "guiding", obstacles: [] });
    expect(p.cutAnchor).toBe(true);
    expect(overlaps(box(p), { x: anchor.x - 4, y: anchor.y - 4, w: anchor.w + 8, h: anchor.h + 8 })).toBe(false);
  });

  it("puts a guiding card at the window's bottom edge when even the anchor leaves no place", () => {
    const target = { x: 0, y: 0, w: 1440, h: 900 };
    const p = place({ card, target, viewport: wide, phone: false, kind: "guiding", obstacles: [] });
    expect(p.side).toBe("edge");
    expect(p.y).toBe(900 - 16 - 160);
    expect(p.arrow).toBeUndefined();
  });

  it("gives a target that fills the phone no dim: its anchor ringed, the card at the bottom", () => {
    const target = { x: 0, y: 0, w: 390, h: 800 }; // the login sheet
    const anchor = { x: 16, y: 300, w: 358, h: 60 };
    const p = place({ card, target, anchor, viewport: phoneView, phone: true, kind: "guiding", obstacles: [] });
    expect(p.dim).toBe(false);
    expect(p.ringAnchor).toBe(true);
    expect(p.side).toBe("edge");
    expect(p.y).toBe(844 - 16 - 160);
  });

  it("keeps the arrow 12px from the card's corners", () => {
    const target = { x: 20, y: 16, w: 100, h: 4 }; // the card clamps down to the top margin
    const p = place({ card, target, viewport: wide, phone: false, kind: "guiding", obstacles: [] });
    expect(p.side).toBe("right");
    expect(p.arrow!.y).toBeGreaterThanOrEqual(12);
    expect(p.arrow!.y).toBeLessThanOrEqual(p.h - 12);
  });
});
