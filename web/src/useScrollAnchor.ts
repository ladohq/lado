// Nothing moves under the pointer (docs/design/ui.md, Models): a section whose blocks grow and
// shrink above the human's place keeps that place on the screen. After each render of the
// section, and whenever its size changes, the anchor noted before is put back where it was by
// scrolling the scrolling container (`.content` above 900 px, the window at or under it) by
// the distance it moved. The anchor is the focused element inside the section, else the one
// last acted on (`hold`, or a pointer press in the section), else the first element in view;
// the nearest `[data-anchor]` around it stands for it, so a row that moves within its card
// keeps the card in place. The human's own scroll is noted, never undone; an anchor gone from
// the page scrolls nothing. `overflow-anchor` is not relied on: Safari has none.
import { type RefObject, useCallback, useEffect, useLayoutEffect, useRef } from "react";

type Held = { el: Element; top: number };

const NARROW = "(max-width: 900px)"; // the app scrolls its window, not `.content`

function scroller(section: HTMLElement): HTMLElement | Window {
  const narrow = typeof window.matchMedia === "function" && window.matchMedia(NARROW).matches;
  return narrow ? window : ((section.closest(".content") as HTMLElement | null) ?? window);
}

const viewTop = (on: HTMLElement | Window) => (on instanceof Window ? 0 : on.getBoundingClientRect().top);

function firstInView(section: HTMLElement): Element | null {
  const top = viewTop(scroller(section));
  for (const el of section.querySelectorAll("*")) if (el.getBoundingClientRect().top >= top) return el;
  return null;
}

export function useScrollAnchor(section: RefObject<HTMLElement | null>): { hold: (acted?: Element | null) => void } {
  const held = useRef<Held | null>(null);
  const acted = useRef<Element | null>(null);

  const note = useCallback(() => {
    const root = section.current;
    held.current = null;
    if (!root) return;
    const focused = document.activeElement;
    const last = acted.current;
    const el =
      focused && focused !== root && root.contains(focused)
        ? focused
        : last && last.isConnected && root.contains(last)
          ? last
          : firstInView(root);
    if (!el) return;
    const around = el.closest("[data-anchor]");
    const anchor = around && root.contains(around) ? around : el;
    held.current = { el: anchor, top: anchor.getBoundingClientRect().top };
  }, [section]);

  // The anchor back at its place, then noted anew.
  const settle = useCallback(() => {
    const root = section.current;
    const was = held.current;
    if (root && was?.el.isConnected) {
      const moved = was.el.getBoundingClientRect().top - was.top;
      if (moved !== 0) scroller(root).scrollBy(0, moved);
    }
    note();
  }, [section, note]);

  useLayoutEffect(settle);

  useEffect(() => {
    const root = section.current;
    if (!root) return;
    const press = (event: Event) => {
      acted.current = event.target as Element;
      note();
    };
    root.addEventListener("pointerdown", press, true);
    root.addEventListener("focusin", note);
    document.addEventListener("scroll", note, { capture: true, passive: true });
    const sized = typeof ResizeObserver === "function" ? new ResizeObserver(settle) : null;
    sized?.observe(root);
    return () => {
      root.removeEventListener("pointerdown", press, true);
      root.removeEventListener("focusin", note);
      document.removeEventListener("scroll", note, { capture: true });
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
