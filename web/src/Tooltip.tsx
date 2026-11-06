// A compact tooltip of the UI's own, instead of the browser's `title` (docs/design/ui.md,
// Structure): it shows TOOLTIP_DELAY_MS after the pointer enters its trigger, and at once
// when the trigger gets the focus from the keyboard; a focus that comes back with the tab
// or window shows nothing. It goes when the pointer leaves, the focus goes, or on Esc.
// While shown, the trigger is described by it (aria-describedby).
// It takes no pointer events and stays inside the window. An arrow on the edge facing the
// trigger points at the trigger's centre. On a touch screen (docs/design/ui.md, Phone
// layout) a tap on a hint (a trigger that is no button or link) shows it at once, and the
// next touch elsewhere hides it; a button's or link's tooltip, which only names it, never
// shows on a tap, not even by the mouse the browser emulates for the tap. A `null` tip stays
// silent: what is up or on its delay goes, and nothing shows until the pointer or the focus
// comes anew.
import {
  cloneElement,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type FocusEvent,
  type MouseEvent,
  type PointerEvent,
  type ReactElement,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

export const TOOLTIP_DELAY_MS = 300;

const GAP = 11; // pixels between the trigger and the tooltip: the arrow's 5 and 6 of room
const MARGIN = 8; // the least room to the window's edge
const ARROW_END = 16; // the least room from the arrow's middle to the card's end, past its corner

// Gives the focus back without a tooltip nobody asked for (the tab bar's trial, Sessions.tsx):
// the focus event comes within `focus()`.
let quiet = false;

export function focusQuietly(element: HTMLElement) {
  quiet = true;
  element.focus({ preventScroll: true });
  quiet = false;
}

// `arrow`: along the edge that faces the trigger, from the card's left or, on the right, its top.
type Place = { left: number; top: number; side: "below" | "above" | "right"; arrow: number };

type Trigger = {
  onMouseEnter?: (event: MouseEvent<HTMLElement>) => void;
  onMouseLeave?: (event: MouseEvent<HTMLElement>) => void;
  onPointerDown?: (event: PointerEvent<HTMLElement>) => void;
  onPointerUp?: (event: PointerEvent<HTMLElement>) => void;
  onFocus?: (event: FocusEvent<HTMLElement>) => void;
  onBlur?: (event: FocusEvent<HTMLElement>) => void;
  "aria-describedby"?: string;
};

export function Tooltip({
  tip,
  side,
  children,
}: {
  tip: ReactNode;
  side?: "right"; // beside the trigger, for a card that must not cover what is under it
  children: ReactElement<Trigger>;
}) {
  const id = useId();
  const [shown, setShown] = useState(false);
  const [place, setPlace] = useState<Place>({ left: 0, top: 0, side: "below", arrow: 0 });
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const trigger = useRef<HTMLElement | null>(null);
  const pressed = useRef(false); // the focus that follows comes from the pointer, not the keyboard
  const touched = useRef(false); // the last press was a touch: the mouse that enters is emulated
  const left = useRef(false); // the last blur was the window's: the focus stayed on the trigger
  const box = useRef<HTMLDivElement>(null);

  const show = (element: HTMLElement) => {
    trigger.current = element;
    setShown(true);
  };
  const hide = () => {
    clearTimeout(timer.current);
    setShown(false);
  };

  useEffect(() => () => clearTimeout(timer.current), []);

  const silent = tip === null;
  useEffect(() => {
    if (silent) hide();
  }, [silent]);

  useEffect(() => {
    if (!shown) return;
    const escape = (event: KeyboardEvent) => event.key === "Escape" && hide();
    // A press elsewhere hides it: a tap shows it with no pointer to leave the trigger.
    const elsewhere = (event: Event) => {
      if (!trigger.current?.contains(event.target as Node)) hide();
    };
    document.addEventListener("keydown", escape);
    document.addEventListener("pointerdown", elsewhere);
    return () => {
      document.removeEventListener("keydown", escape);
      document.removeEventListener("pointerdown", elsewhere);
    };
  }, [shown]);

  // With `side="right"` beside the trigger when the window has room there, centred on it and
  // moved no further than the window asks. Else under the trigger, or over it when it does
  // not fit below and there is more room over it; from the trigger's left, but far enough
  // left for the arrow to reach a narrow trigger's centre. Never past the window's edge. The
  // arrow points at the trigger's centre, kept off the card's corners.
  useLayoutEffect(() => {
    if (!shown || !trigger.current || !box.current) return;
    const at = trigger.current.getBoundingClientRect();
    const size = box.current.getBoundingClientRect();
    const inWindow = (top: number) => Math.max(MARGIN, Math.min(top, window.innerHeight - size.height - MARGIN));
    const aside = at.right + GAP;
    if (side === "right" && aside + size.width <= window.innerWidth - MARGIN) {
      const middle = at.top + at.height / 2;
      const top = inWindow(middle - size.height / 2);
      const arrow = Math.max(ARROW_END, Math.min(middle - top, size.height - ARROW_END));
      setPlace({ left: aside, top, side: "right", arrow });
      return;
    }
    const centre = at.left + at.width / 2;
    const wanted = Math.min(at.left, centre - ARROW_END);
    const left = Math.max(MARGIN, Math.min(wanted, window.innerWidth - size.width - MARGIN));
    const below = at.bottom + GAP;
    const under = window.innerHeight - MARGIN - below;
    const over = at.top - GAP - MARGIN;
    const vertical = size.height > under && over > under ? "above" : "below";
    const top = vertical === "below" ? below : at.top - GAP - size.height;
    const arrow =
      size.width < 2 * ARROW_END
        ? size.width / 2
        : Math.max(ARROW_END, Math.min(centre - left, size.width - ARROW_END));
    setPlace({ left, top: inWindow(top), side: vertical, arrow });
  }, [shown, side]);

  const own = children.props;
  const element = cloneElement(children, {
    "aria-describedby": shown ? id : own["aria-describedby"],
    onMouseEnter: (event) => {
      own.onMouseEnter?.(event);
      if (touched.current || silent) return;
      const target = event.currentTarget;
      clearTimeout(timer.current);
      timer.current = setTimeout(() => show(target), TOOLTIP_DELAY_MS);
    },
    onMouseLeave: (event) => {
      own.onMouseLeave?.(event);
      touched.current = false; // the tap's mouse left: the next to enter may be a real one
      hide();
    },
    onPointerDown: (event) => {
      own.onPointerDown?.(event);
      pressed.current = true;
      touched.current = event.pointerType === "touch";
    },
    onPointerUp: (event) => {
      own.onPointerUp?.(event);
      if (event.pointerType !== "touch" || event.currentTarget.matches("button, a, [role=button]")) return;
      clearTimeout(timer.current);
      show(event.currentTarget);
    },
    onFocus: (event) => {
      own.onFocus?.(event);
      const target = event.currentTarget;
      // From nowhere after the window's blur: the window is back. A focus from an element
      // is the keyboard's, even when the window took this trigger's focus before.
      const returned = left.current && !event.relatedTarget;
      // A focus given by code after a press elsewhere (Details' Copy path) is no keyboard's.
      const keyboard = !pressed.current && (!target.matches(":focus") || target.matches(":focus-visible"));
      if (keyboard && !returned && !quiet && !silent) show(target);
      pressed.current = false;
    },
    onBlur: (event) => {
      own.onBlur?.(event);
      left.current = document.activeElement === event.currentTarget;
      hide();
    },
  });

  return (
    <>
      {element}
      {shown &&
        createPortal(
          <div
            ref={box}
            id={id}
            role="tooltip"
            className="tooltip"
            data-side={place.side}
            style={
              {
                left: place.left,
                top: place.top,
                [place.side === "right" ? "--arrow-y" : "--arrow-x"]: `${place.arrow}px`,
              } as CSSProperties
            }
          >
            {tip}
          </div>,
          document.body,
        )}
    </>
  );
}
