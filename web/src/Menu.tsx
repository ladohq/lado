// A menu of the UI's own (role=menu): the first item gets the focus, the arrow keys move
// it, Esc closes; `useDismiss` closes it, or a popover, on a press outside. An item is a
// button or a link, which opens in a new tab; both are menuitems.
import { useEffect, useLayoutEffect, useState, type CSSProperties, type RefObject } from "react";

export type MenuItem = { label: string; onSelect: () => void } | { label: string; href: string };

const MARGIN = 8; // between a popover and the window's edges

// Where a popover `width` wide goes in a window `viewport` wide: 6px under `anchor`, from
// its left edge, or with `end` to its right edge; moved along so it stays MARGIN inside
// both of the window's edges, the anchor's side first when it is wider than the window.
export function placeBelow(
  anchor: { left: number; right: number; bottom: number },
  width: number,
  viewport: number,
  end = false,
): CSSProperties {
  const top = anchor.bottom + 6;
  const room = viewport - MARGIN - width; // the farthest a popover's far edge may be from the window's
  return end
    ? { position: "fixed", top, right: Math.max(MARGIN, Math.min(viewport - anchor.right, room)), left: "auto" }
    : { position: "fixed", top, left: Math.max(MARGIN, Math.min(anchor.left, room)), right: "auto" };
}

// Where the menu or popover `floating` goes: fixed under `anchor`, so a scrolling box
// around it (the session list, the session's page) does not cut it, and inside the window
// (placeBelow). Placed again after each render, as what it shows may change its width.
export function useBelow(
  anchor: RefObject<HTMLElement | null>,
  floating: RefObject<HTMLElement | null>,
  open: boolean,
  end = false,
): CSSProperties | undefined {
  const [style, setStyle] = useState<CSSProperties | undefined>(undefined);
  useLayoutEffect(() => {
    const box = anchor.current?.getBoundingClientRect();
    if (!open || !box) return;
    const placed = placeBelow(box, floating.current?.offsetWidth ?? 0, window.innerWidth, end);
    setStyle((now) => (JSON.stringify(now) === JSON.stringify(placed) ? now : placed));
  });
  return style;
}

// Closes on a press outside `box`.
export function useDismiss(open: boolean, box: RefObject<HTMLElement | null>, close: () => void) {
  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) close();
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open, box, close]);
}

export function Menu({
  label,
  ref: menu,
  style,
  items,
  onClose,
}: {
  label: string;
  ref: RefObject<HTMLDivElement | null>; // the menu, for useBelow
  style?: CSSProperties;
  items: MenuItem[];
  onClose: () => void;
}) {
  const entries = () => [...(menu.current?.querySelectorAll<HTMLElement>("[role=menuitem]") ?? [])];
  useEffect(() => {
    entries()[0]?.focus();
  }, []);
  return (
    <div
      ref={menu}
      role="menu"
      aria-label={label}
      className="action-menu"
      style={style}
      onKeyDown={(event) => {
        const all = entries();
        const at = all.indexOf(document.activeElement as HTMLElement);
        if (event.key === "Escape") {
          event.preventDefault();
          onClose();
        } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault();
          const step = event.key === "ArrowDown" ? 1 : -1;
          all[(at + step + all.length) % all.length]?.focus();
        }
      }}
    >
      {items.map((item) =>
        "href" in item ? (
          <a key={item.label} role="menuitem" href={item.href} target="_blank" rel="noopener" onClick={onClose}>
            {item.label}
          </a>
        ) : (
          <button key={item.label} type="button" role="menuitem" onClick={item.onSelect}>
            {item.label}
          </button>
        ),
      )}
    </div>
  );
}
