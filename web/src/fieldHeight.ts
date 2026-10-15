// The height of a text field that grows with its text (the composer, the waiting card's
// fields, a gate's comment): one rule for all of them.
import { useLayoutEffect, useRef, type RefObject } from "react";

// The lines the composer's field, and every field that grows like it, grows to before it
// scrolls.
export const MOST_LINES = 8;

// The lines the waiting card's fields and a gate's comment open with.
export const CARD_LINES = 3;

// The field as tall as its text, from `least` lines to `most`, then it scrolls inside. Lines
// count by the field's computed line height; its padding and border come on top. Returns
// the height it set, in pixels.
export function grow(field: HTMLTextAreaElement, least: number, most: number): number {
  const style = getComputedStyle(field);
  const line = parseFloat(style.lineHeight) || 20;
  const padding = (parseFloat(style.paddingTop) || 0) + (parseFloat(style.paddingBottom) || 0);
  const border = (parseFloat(style.borderTopWidth) || 0) + (parseFloat(style.borderBottomWidth) || 0);
  const top = line * most + padding;
  field.style.height = "auto";
  const height = field.scrollHeight;
  const set = Math.max(line * least + padding, Math.min(height, top)) + border;
  field.style.height = `${set}px`;
  field.style.overflowY = height > top ? "auto" : "hidden";
  return set;
}

// `grow` on each change of the text. A field with the focus that grew brings its lower edge
// into view: the nearest box that scrolls (the waiting card's list, else the page) moves by
// as much as the field passed its edge.
export function useGrow(field: RefObject<HTMLTextAreaElement | null>, text: string, least: number, most: number) {
  const before = useRef(0);
  useLayoutEffect(() => {
    const box = field.current;
    if (!box) return;
    const height = grow(box, least, most);
    if (height > before.current && before.current > 0 && document.activeElement === box) {
      box.scrollIntoView?.({ block: "nearest" });
    }
    before.current = height;
  }, [field, text, least, most]);
}
