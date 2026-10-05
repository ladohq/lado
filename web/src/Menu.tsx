// A menu of the UI's own (role=menu): the first item gets the focus, the arrow keys move
// it, Esc closes; `useDismiss` closes it, or a popover, on a press outside. An item is a
// button or a link, which opens in a new tab; both are menuitems.
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from "react";

export type MenuItem = { label: string; onSelect: () => void } | { label: string; href: string };

// Where a menu or popover goes: fixed under `anchor`, so a scrolling box around it (the
// session list, the session's page) does not cut it; from the anchor's left edge, or with
// `end` to its right edge.
export function useBelow(
  anchor: RefObject<HTMLElement | null>,
  open: boolean,
  end = false,
): CSSProperties | undefined {
  const [style, setStyle] = useState<CSSProperties | undefined>(undefined);
  useLayoutEffect(() => {
    const box = anchor.current?.getBoundingClientRect();
    if (!open || !box) return;
    const top = box.bottom + 6;
    setStyle(
      end
        ? { position: "fixed", top, right: Math.max(8, window.innerWidth - box.right), left: "auto" }
        : { position: "fixed", top, left: Math.max(8, box.left), right: "auto" },
    );
  }, [anchor, open, end]);
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
  style,
  items,
  onClose,
}: {
  label: string;
  style?: CSSProperties;
  items: MenuItem[];
  onClose: () => void;
}) {
  const menu = useRef<HTMLDivElement>(null);
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
