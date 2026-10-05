// Copying a text for the human (docs/design/ui.md, Launch and session control): a session's
// link from its list row's menu and its head, its folder from its head. The Clipboard API
// first, then what was copied is said for COPIED_MS in the caller's role="status". Without
// the API (a page not served from localhost or https) or when the copy is refused, the
// text is shown selected, to copy by hand.
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

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
    try {
      if (!navigator.clipboard) throw new Error("no Clipboard API");
      await navigator.clipboard.writeText(text);
      setNote(copied);
      return true;
    } catch {
      return false;
    }
  };
  return { note, copy };
}

// The text selected in a field, to copy by hand; Esc closes it.
export function CopyField({
  title,
  label,
  text,
  style,
  onClose,
}: {
  title: string; // the dialog's name: "Link to lado"
  label: string; // the field's: "Link"
  text: string;
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
  const close = () => {
    setShown(false);
    button.current?.focus();
  };
  useDismiss(shown, box, () => setShown(false));
  const below = useBelow(box, shown);
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
      {shown && <CopyField title={field.title} label={field.label} text={text} style={below} onClose={close} />}
    </span>
  );
}
