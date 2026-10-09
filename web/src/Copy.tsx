// Copying a text for the human (docs/design/ui.md, Launch and session control): a session's
// link from its list row's menu and its head, its folder from its head, a kit's address or
// folder from its card's menu (RowMenu.tsx). The Clipboard API
// first; without it (a page not served from localhost or https) or when it refuses, the
// legacy copy (execCommand); what was copied is said for COPIED_MS in the caller's
// role="status". Only when both fail is the text shown selected, to copy by hand.
import { useEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from "react";

import { useBelow, useDismiss } from "./Menu";
import { Tooltip } from "./Tooltip";

export const COPIED_MS = 2000; // how long "Link copied" stays

// `note` is what was copied last, for COPIED_MS; `copy` resolves false when the text
// could not be copied, for the caller to show it in a CopyField.
export function useCopy() {
  const [note, setNote] = useState("");
  useEffect(() => {
    if (!note) return;
    const timer = setTimeout(() => setNote(""), COPIED_MS);
    return () => clearTimeout(timer);
  }, [note]);
  const copy = async (text: string, copied: string) => {
    let done = false;
    // Without the API the legacy copy runs at once, still within the click.
    if (navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(text);
        done = true;
      } catch {
        done = legacyCopy(text);
      }
    } else done = legacyCopy(text);
    if (done) setNote(copied);
    return done;
  };
  return { note, copy };
}

// document.execCommand("copy") of the text selected in a hidden field, which works also
// where the Clipboard API does not exist; the focus goes back where it was, and the page
// does not scroll.
function legacyCopy(text: string) {
  const focused = document.activeElement;
  const field = document.createElement("textarea");
  field.value = text;
  field.readOnly = true;
  field.setAttribute("aria-hidden", "true");
  Object.assign(field.style, { position: "fixed", top: "0", left: "-9999px", opacity: "0" });
  document.body.append(field);
  try {
    field.focus({ preventScroll: true });
    field.select();
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    field.remove();
    if (focused instanceof HTMLElement) focused.focus({ preventScroll: true });
  }
}

// The text selected in a field, to copy by hand; Esc closes it.
export function CopyField({
  title,
  label,
  text,
  ref,
  style,
  onClose,
}: {
  title: string; // the dialog's name: "Link to lado"
  label: string; // the field's: "Link"
  text: string;
  ref: RefObject<HTMLDivElement | null>; // the dialog, for useBelow
  style?: CSSProperties;
  onClose: () => void;
}) {
  const field = useRef<HTMLInputElement>(null);
  useEffect(() => {
    field.current?.focus();
    field.current?.select();
  }, []);
  return (
    <div
      ref={ref}
      role="dialog"
      aria-label={title}
      className="popover link-popover"
      style={style}
      onKeyDown={(event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        onClose();
      }}
    >
      <input ref={field} type="text" readOnly aria-label={label} value={text} />
      <p className="muted">Press ⌘C / Ctrl+C to copy</p>
    </div>
  );
}

// An icon button that copies `text`, with its tooltip, its note and, when the copy fails,
// the field below it.
export function CopyButton({
  label,
  copied,
  text,
  field,
  icon,
  className = "",
}: {
  label: string; // "Copy link": the button's name and tooltip
  copied: string; // "Link copied"
  text: string;
  field: { title: string; label: string };
  icon: ReactNode;
  className?: string;
}) {
  const { note, copy } = useCopy();
  const [shown, setShown] = useState(false);
  const box = useRef<HTMLSpanElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const popover = useRef<HTMLDivElement>(null);
  const close = () => {
    setShown(false);
    button.current?.focus();
  };
  useDismiss(shown, box, () => setShown(false));
  const below = useBelow(box, popover, shown);
  return (
    <span ref={box} className={`copy-button ${className}`.trim()}>
      <Tooltip tip={label}>
        <button
          ref={button}
          type="button"
          className="icon-button"
          aria-label={label}
          onClick={async () => setShown(!(await copy(text, copied)))}
        >
          {icon}
        </button>
      </Tooltip>
      <span role="status" className="row-note">
        {note}
      </span>
      {shown && <CopyField title={field.title} label={field.label} text={text} ref={popover} style={below} onClose={close} />}
    </span>
  );
}
