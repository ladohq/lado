// Nothing moves under the pointer (docs/design/ui.md, Models): a section whose blocks grow and
// shrink above the human's place keeps that place on the screen. After each render of the
// section, and whenever its size changes, the anchor noted before is put back where it was by
// scrolling the scrolling container (`.content` above 900 px, the window at or under it) by
// the distance it moved. The anchor is the focused element inside the section, else the one
// last acted on (`hold`, or a pointer press in the section), else the first element in view.
// When it leaves the page (× turns into Undo, a field into a name, a server into its line), the
// nearest `[data-anchor]` that held it stands for it, so a card or a server's row keeps its
// place. The page scrolls by whole pixels: an anchor keeps the place first noted, so the half
// pixels of one change and the next do not add up. The human's own scroll is noted, never
// undone; an anchor gone with nothing around it scrolls nothing. `overflow-anchor` is not
// relied on: Safari has none.
import { type RefObject, useCallback, useEffect, useLayoutEffect, useRef } from "react";

type Spot = { el: Element; top: number };
type Held = { own: Spot; around: Spot | null };
type Scroller = HTMLElement | Window;

const NARROW = "(max-width: 900px)"; // the app scrolls its window, not `.content`

function scroller(section: HTMLElement): Scroller {
  const narrow = typeof window.matchMedia === "function" && window.matchMedia(NARROW).matches;
  return narrow ? window : ((section.closest(".content") as HTMLElement | null) ?? window);
}

const viewTop = (on: Scroller) => (on === window ? 0 : (on as HTMLElement).getBoundingClientRect().top);
const position = (on: Scroller) => (on === window ? window.scrollY : (on as HTMLElement).scrollTop);

function firstInView(section: HTMLElement): Element | null {
  const top = viewTop(scroller(section));
  for (const el of section.querySelectorAll("*")) if (el.getBoundingClientRect().top >= top) return el;
  return null;
}

export function useScrollAnchor(section: RefObject<HTMLElement | null>): {
  hold: (acted?: Element | null) => void;
} {
  const held = useRef<Held | null>(null);
  const acted = useRef<Element | null>(null);
  const ours = useRef<{ on: Scroller; at: number } | null>(null); // the scroll it made last

  // The anchor now; an element `kept` held already keeps the place noted for it then.
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
            : (gone ?? firstInView(root)); // what held it, while the change goes on
      if (!el) return;
      // What holds the anchor is noted where it is now: only the anchor keeps its first place.
      const now = (at: Element): Spot => ({ el: at, top: at.getBoundingClientRect().top });
      const own = (kept?.own.el === el ? kept.own : kept?.around?.el === el ? kept.around : null) ?? now(el);
      const around = el.closest("[data-anchor]");
      held.current = { own, around: around && around !== el && root.contains(around) ? now(around) : null };
    },
    [section],
  );

  // The anchor back at its place, then noted anew.
  const settle = useCallback(() => {
    const root = section.current;
    const at = held.current;
    const was = at?.own.el.isConnected ? at.own : at?.around?.el.isConnected ? at.around : null;
    if (root && was) {
      const moved = was.el.getBoundingClientRect().top - was.top;
      if (Math.abs(moved) >= 1) {
        const on = scroller(root);
        on.scrollBy(0, moved);
        ours.current = { on, at: position(on) };
      }
    }
    note(at);
  }, [section, note]);

  useLayoutEffect(settle);

  useEffect(() => {
    const root = section.current;
    if (!root) return;
    // A press or a focus on what is held already keeps its place; a scroll the human made is a
    // new place, the one this hook made is not.
    const press = (event: Event) => {
      acted.current = event.target as Element;
      note(held.current);
    };
    const fresh = () => note(held.current);
    const scrolled = (event: Event) => {
      const mine = ours.current;
      const on = event.target === document ? window : event.target;
      if (mine && on === mine.on) {
        ours.current = null;
        if (position(mine.on) === mine.at) return;
      }
      note();
    };
    root.addEventListener("pointerdown", press, true);
    root.addEventListener("focusin", fresh);
    document.addEventListener("scroll", scrolled, { capture: true, passive: true });
    const sized = typeof ResizeObserver === "function" ? new ResizeObserver(settle) : null;
    sized?.observe(root);
    return () => {
      root.removeEventListener("pointerdown", press, true);
      root.removeEventListener("focusin", fresh);
      document.removeEventListener("scroll", scrolled, { capture: true });
      sized?.disconnect();
    };
  }, [section, note, settle]);

  const hold = useCallback(
    (el?: Element | null) => {
      acted.current = el ?? null;
      note();
    },
    [note],
  );
  return { hold };
}
