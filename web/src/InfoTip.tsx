// The info button beside a label (docs/design/ui.md, Launch and session control): an
// explanation the human does not need to act, shown on a press, never on hover. A press,
// Enter or Space opens and closes it; Esc closes it and only it (the window around it stays);
// a press outside, another info button or Tab away closes it. Its text is put in a status
// region while open, so a screen reader reads it with the focus kept on the button.
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { useBelow, useDismiss } from "./Menu";

// The open one closes when another opens: one explanation at a time.
let closeOpen: (() => void) | null = null;

export function InfoTip({ about, children }: { about: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const wrap = useRef<HTMLSpanElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const pop = useRef<HTMLSpanElement>(null);
  const style = useBelow(button, pop, open);
  useDismiss(open, wrap, () => setOpen(false));
  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    if (closeOpen) closeOpen();
    closeOpen = close;
    return () => {
      if (closeOpen === close) closeOpen = null;
    };
  }, [open]);
  return (
    <span className="info-wrap" ref={wrap}>
      <button
        ref={button}
        type="button"
        className="info-tip"
        aria-label={`About ${about}`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((was) => !was)}
        onKeyDown={(event) => {
          if (event.key === "Escape" && open) {
            event.preventDefault(); // the window's Esc sees it taken
            setOpen(false);
          }
        }}
        onBlur={(event) => {
          if (!wrap.current?.contains(event.relatedTarget as Node | null)) setOpen(false);
        }}
      >
        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
          <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.3" />
          <path d="M8 7.2v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          <circle cx="8" cy="4.9" r=".9" fill="currentColor" />
        </svg>
      </button>
      <span ref={pop} id={id} role="status" className={open ? "info-pop" : "info-shut"} style={open ? style : undefined}>
        {open ? children : null}
      </span>
    </span>
  );
}
