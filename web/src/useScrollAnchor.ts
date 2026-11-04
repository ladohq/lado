// Nothing moves under the pointer (docs/design/ui.md, Models): when the human acts in a
// section whose blocks grow and shrink above the place acted on, that place stays on the
// screen. The anchor is the focused element inside the section, else the one last pressed
// there (a button a click does not focus, as Safari's) until a press elsewhere; with neither,
// nothing is held and the hook never scrolls. Its place is its distance from the section's top, so whatever moves the
// whole section (a section above growing, the window resized, the human's scroll, the hook's
// own) changes nothing; after each render of the section, and whenever its size changes, the
// scrolling container (`.content` above 900 px, the window at or under it) is scrolled by what
// that distance gained. When the anchor leaves the page (× turned into Undo, a field into a
// name, a server into its line), the nearest `[data-anchor]` that held it stands for it. The
// page scrolls by whole pixels: the anchor keeps the distance it was first noted at, so half
// pixels do not add up; a scroll inside the section (a list's own) notes it anew.
// `overflow-anchor` is not relied on: Safari has none.
import { type RefObject, useCallback, useEffect, useLayoutEffect, useRef } from "react";

type Spot = { el: Element; at: number }; // `at`: its top less the section's
type Held = { own: Spot; around: Spot | null };

const NARROW = "(max-width: 900px)"; // the app scrolls its window, not `.content`

type Scroller = HTMLElement | Window;

function scroller(section: HTMLElement): Scroller {
  const narrow = typeof window.matchMedia === "function" && window.matchMedia(NARROW).matches;
  return narrow ? window : ((section.closest(".content") as HTMLElement | null) ?? window);
}

const position = (on: Scroller) => (on === window ? window.scrollY : (on as HTMLElement).scrollTop);

export function useScrollAnchor(section: RefObject<HTMLElement | null>): void {
  const held = useRef<Held | null>(null);
  const acted = useRef<Element | null>(null);
  // Where the hook scrolled last: the exact place it wants (`want`) and where the page, which
  // scrolls by whole pixels, put it (`left`); a page found elsewhere was scrolled by another.
  const ours = useRef<{ on: Scroller; want: number; left: number } | null>(null);

  // The anchor now; an element `kept` held already keeps the distance noted for it then.
  const note = useCallback(
    (kept?: Held | null) => {
      const root = section.current;
      held.current = null;
      if (!root) return;
      const focused = document.activeElement;
      const last = acted.current;
      const gone = kept && !kept.own.el.isConnected && kept.around?.el.isConnected ? kept.around.el : null;
      const el =
        focused && focused !== root && root.contains(focused)
          ? focused
          : last && last.isConnected && root.contains(last)
            ? last
            : gone; // what held it, while the change goes on
      if (!el) return;
      const top = root.getBoundingClientRect().top;
      const now = (spot: Element): Spot => ({ el: spot, at: spot.getBoundingClientRect().top - top });
      const own = (kept?.own.el === el ? kept.own : kept?.around?.el === el ? kept.around : null) ?? now(el);
      const around = el.closest("[data-anchor]");
      held.current = { own, around: around && around !== el && root.contains(around) ? now(around) : null };
    },
    [section],
  );

  // The anchor back at its distance from the section's top, then noted anew.
  const settle = useCallback(() => {
    const root = section.current;
    const was = held.current;
    const spot = was?.own.el.isConnected ? was.own : was?.around?.el.isConnected ? was.around : null;
    if (root && spot) {
      const moved = spot.el.getBoundingClientRect().top - root.getBoundingClientRect().top - spot.at;
      if (moved !== 0) {
        const on = scroller(root);
        const last = ours.current;
        const now = position(on);
        // The place it wanted, while the page is where that put it and it put it there (a scroll
        // stopped at the top or the bottom is no place wanted): else where the page is.
        const kept = last && last.on === on && Math.abs(now - last.left) < 1 && Math.abs(last.left - last.want) < 1;
        const want = (kept ? last.want : now) + moved;
        on.scrollTo(0, want);
        ours.current = { on, want, left: position(on) };
        spot.at += moved; // made up for: the distance it has now
      }
    }
    note(was);
  }, [section, note]);

  useLayoutEffect(settle);

  useEffect(() => {
    const root = section.current;
    if (!root) return;
    // A press or a focus on what is held already keeps its distance; a scroll inside the
    // section moves things within it, so what it moved is noted where it is now.
    // A press elsewhere on the page: the human is no longer in the section.
    const press = (event: Event) => {
      const inside = root.contains(event.target as Node);
      acted.current = inside ? (event.target as Element) : null;
      note(inside ? held.current : null);
    };
    const fresh = () => note(held.current);
    const scrolled = () => note();
    document.addEventListener("pointerdown", press, true);
    root.addEventListener("focusin", fresh);
    root.addEventListener("scroll", scrolled, { capture: true, passive: true });
    const sized = typeof ResizeObserver === "function" ? new ResizeObserver(settle) : null;
    sized?.observe(root);
    return () => {
      document.removeEventListener("pointerdown", press, true);
      root.removeEventListener("focusin", fresh);
      root.removeEventListener("scroll", scrolled, { capture: true });
      sized?.disconnect();
    };
  }, [section, note, settle]);
}

const ACTS = ["pointerdown", "wheel", "touchstart", "keydown"] as const;

// The page opened at the section's anchor: the section at the top of what scrolls, put back
// there whenever the page around it changes size (a section above growing once its check
// ends), until the human presses, scrolls or types anywhere; what it returns stops it too.
export function keepAtTop(section: HTMLElement): () => void {
  const put = () => section.scrollIntoView({ block: "start" });
  put();
  const page = section.parentElement;
  const sized = typeof ResizeObserver === "function" && page ? new ResizeObserver(put) : null;
  if (page) sized?.observe(page);
  const stop = () => {
    sized?.disconnect();
    for (const act of ACTS) document.removeEventListener(act, stop, true);
  };
  for (const act of ACTS) document.addEventListener(act, stop, { capture: true, passive: true });
  return stop;
}
