// Whether a box shows all it holds (the waiting card's report and recommendation, its
// choices, a cut head), measured anew as it scrolls, resizes or its content changes.
import { useCallback, useLayoutEffect, useRef, useState, type RefObject } from "react";

// Runs `changed` now and whenever `box` or its first child is laid out anew.
function useLaidOut(box: RefObject<HTMLElement | null>, changed: () => void) {
  useLayoutEffect(changed); // a change of the content a render makes
  useLayoutEffect(() => {
    const element = box.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(changed);
    observer.observe(element);
    if (element.firstElementChild) observer.observe(element.firstElementChild);
    return () => observer.disconnect();
  }, [box, changed]);
}

// Whether a box that scrolls has more below what it shows, and the `scrolled` to call on its
// scroll. A pixel of slack: a zoomed page rounds the heights.
export function useMore<T extends HTMLElement>() {
  const box = useRef<T>(null);
  const [more, setMore] = useState(false);
  const scrolled = useCallback(() => {
    const element = box.current;
    if (element) setMore(element.scrollTop + element.clientHeight < element.scrollHeight - 1);
  }, [box]);
  useLaidOut(box, scrolled);
  return { box, more, scrolled };
}

// Whether a text its stylesheet cuts on one line is cut.
export function useClamped<T extends HTMLElement>() {
  const text = useRef<T>(null);
  const [clamped, setClamped] = useState(false);
  const measure = useCallback(() => {
    const element = text.current;
    if (element) setClamped(element.scrollWidth > element.clientWidth + 1);
  }, []);
  useLaidOut(text, measure);
  return { text, clamped };
}
