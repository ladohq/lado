// A menu of the UI's own (role=menu): the first item gets the focus, the arrow keys move
// it, Esc closes; `useDismiss` closes it, or a popover, on a press outside. An item is a
// button or a link, which opens in a new tab; both are menuitems. An item may have an icon
// (a link with one then shows ↗) and a line above it (`divided`).
import {
  Fragment,
  useEffect,
  useLayoutEffect,
  useState,
  type CSSProperties,
  type ReactNode,
  type RefObject,
} from "react";

type ItemLook = { label: string; icon?: ReactNode; divided?: boolean };
export type MenuItem = (ItemLook & { onSelect: () => void }) | (ItemLook & { href: string });

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

// Where a menu `size` big goes beside a rail item `anchor`: right of it, its bottom on the
// anchor's bottom, kept MARGIN inside the window (Help on the rail).
export function placeBeside(
  anchor: { right: number; bottom: number },
  size: { width: number; height: number },
  viewport: { width: number; height: number },
): CSSProperties {
  const left = Math.min(anchor.right + MARGIN, viewport.width - MARGIN - size.width);
  const top = Math.min(anchor.bottom - size.height, viewport.height - MARGIN - size.height);
  return { position: "fixed", left: Math.max(MARGIN, left), top: Math.max(MARGIN, top), bottom: "auto" };
}

// Where the menu `floating` goes beside `anchor` (placeBeside): past the right edge of the
// rail that holds it, its bottom on the anchor's; fixed, so nothing around cuts it; placed
// again after each render.
export function useBeside(
  anchor: RefObject<HTMLElement | null>,
  floating: RefObject<HTMLElement | null>,
  open: boolean,
): CSSProperties | undefined {
  const [style, setStyle] = useState<CSSProperties | undefined>(undefined);
  useLayoutEffect(() => {
    const box = anchor.current?.getBoundingClientRect();
    if (!open || !box) return;
    const right = (anchor.current?.closest(".rail") ?? anchor.current)!.getBoundingClientRect().right;
    const size = { width: floating.current?.offsetWidth ?? 0, height: floating.current?.offsetHeight ?? 0 };
    const placed = placeBeside({ right, bottom: box.bottom }, size, { width: window.innerWidth, height: window.innerHeight });
    setStyle((now) => (JSON.stringify(now) === JSON.stringify(placed) ? now : placed));
  });
  return open ? style : undefined;
}

// Whether Esc belongs to a layer over the page, not to an expanded card or panel under it: a
// dialog, a menu or the title's field the focus is in, or Details or the team's list, the
// popovers that hear Esc with the focus outside them.
export function escapeIsTaken(target: EventTarget | null): boolean {
  if (target instanceof Element && target.closest("dialog, [role=dialog], [role=menu], .title-edit")) return true;
  return document.querySelector(".session-popover, .team-popover") !== null;
}

// Closes on a press outside `box`; `close` gets the press, to see what was pressed.
export function useDismiss(open: boolean, box: RefObject<HTMLElement | null>, close: (event: MouseEvent) => void) {
  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) close(event);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open, box, close]);
}

export function Menu({
  label,
  ref: menu,
  style,
  className,
  items,
  onClose,
}: {
  label: string;
  ref: RefObject<HTMLDivElement | null>; // the menu, for useBelow
  style?: CSSProperties;
  className?: string;
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
      className={`action-menu${className ? ` ${className}` : ""}`}
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
      {items.map((item) => (
        <Fragment key={item.label}>
          {item.divided && <hr />}
          {"href" in item ? (
            <a role="menuitem" href={item.href} target="_blank" rel="noopener" onClick={onClose}>
              {item.icon}
              {item.icon ? <span>{item.label}</span> : item.label}
              {item.icon && (
                <span className="menu-out" aria-hidden="true">
                  ↗
                </span>
              )}
            </a>
          ) : (
            <button type="button" role="menuitem" onClick={item.onSelect}>
              {item.icon}
              {item.icon ? <span>{item.label}</span> : item.label}
            </button>
          )}
        </Fragment>
      ))}
    </div>
  );
}
