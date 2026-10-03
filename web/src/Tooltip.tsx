// A compact tooltip of the UI's own, instead of the browser's `title` (docs/design/ui.md,
// Structure): it shows TOOLTIP_DELAY_MS after the pointer enters its trigger, and at once
// when the trigger gets the focus from the keyboard; it goes when the pointer leaves, the
// focus goes, or on Esc. While shown, the trigger is described by it (aria-describedby).
// It takes no pointer events and stays inside the window.
import {
  cloneElement,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type FocusEvent,
  type MouseEvent,
  type PointerEvent,
  type ReactElement,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

export const TOOLTIP_DELAY_MS = 300;

const GAP = 6; // pixels between the trigger and the tooltip
const MARGIN = 8; // the least room to the window's edge

type Trigger = {
  onMouseEnter?: (event: MouseEvent<HTMLElement>) => void;
  onMouseLeave?: (event: MouseEvent<HTMLElement>) => void;
  onPointerDown?: (event: PointerEvent<HTMLElement>) => void;
  onFocus?: (event: FocusEvent<HTMLElement>) => void;
  onBlur?: (event: FocusEvent<HTMLElement>) => void;
  "aria-describedby"?: string;
};

export function Tooltip({ tip, children }: { tip: ReactNode; children: ReactElement<Trigger> }) {
  const id = useId();
  const [shown, setShown] = useState(false);
  const [place, setPlace] = useState({ left: 0, top: 0 });
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const trigger = useRef<HTMLElement | null>(null);
  const pressed = useRef(false); // the focus that follows comes from the pointer, not the keyboard
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

  useEffect(() => {
    if (!shown) return;
    const escape = (event: KeyboardEvent) => event.key === "Escape" && hide();
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [shown]);

  // Under the trigger, or over it when there is no room below; never past the window's edge.
  useLayoutEffect(() => {
    if (!shown || !trigger.current || !box.current) return;
    const at = trigger.current.getBoundingClientRect();
    const size = box.current.getBoundingClientRect();
    const left = Math.max(MARGIN, Math.min(at.left, window.innerWidth - size.width - MARGIN));
    const below = at.bottom + GAP;
    const top = below + size.height > window.innerHeight - MARGIN ? at.top - GAP - size.height : below;
    setPlace({ left, top: Math.max(MARGIN, top) });
  }, [shown]);

  const own = children.props;
  const element = cloneElement(children, {
    "aria-describedby": shown ? id : own["aria-describedby"],
    onMouseEnter: (event) => {
      own.onMouseEnter?.(event);
      const target = event.currentTarget;
      clearTimeout(timer.current);
      timer.current = setTimeout(() => show(target), TOOLTIP_DELAY_MS);
    },
    onMouseLeave: (event) => {
      own.onMouseLeave?.(event);
      hide();
    },
    onPointerDown: (event) => {
      own.onPointerDown?.(event);
      pressed.current = true;
    },
    onFocus: (event) => {
      own.onFocus?.(event);
      if (!pressed.current) show(event.currentTarget);
      pressed.current = false;
    },
    onBlur: (event) => {
      own.onBlur?.(event);
      hide();
    },
  });

  return (
    <>
      {element}
      {shown &&
        createPortal(
          <div ref={box} id={id} role="tooltip" className="tooltip" style={place}>
            {tip}
          </div>,
          document.body,
        )}
    </>
  );
}
