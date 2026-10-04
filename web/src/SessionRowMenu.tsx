// A session list row's menu (docs/design/ui.md, Launch and session control): actions on the
// entry only, and only ones that work: Copy link and Open in new tab. The session's own
// actions are in its head (SessionControl.tsx). The link is the page's address without the
// token: the login is the browser's cookie. Without the Clipboard API (a page not served
// from localhost or https) or when the copy is refused, the address is shown selected, to
// copy by hand; "Link copied" is said in the row, outside the menu, which closes.
import { useEffect, useRef, useState, type CSSProperties } from "react";

import { Menu, useBelow, useDismiss } from "./Menu";
import { sessionPath } from "./paths";

const NOTE_MS = 2000; // how long "Link copied" stays

export function SessionRowMenu({ name }: { name: string }) {
  const [shown, setShown] = useState<"menu" | "link" | null>(null);
  const [note, setNote] = useState("");
  const box = useRef<HTMLDivElement>(null);
  const more = useRef<HTMLButtonElement>(null);
  const close = () => setShown(null);
  useDismiss(shown !== null, box, close);
  const below = useBelow(box, shown !== null);
  const link = `${window.location.origin}${sessionPath(name)}`;

  useEffect(() => {
    if (!note) return;
    const timer = setTimeout(() => setNote(""), NOTE_MS);
    return () => clearTimeout(timer);
  }, [note]);

  const back = () => {
    close();
    more.current?.focus();
  };
  const copy = async () => {
    try {
      if (!navigator.clipboard) throw new Error("no Clipboard API");
      await navigator.clipboard.writeText(link);
      setNote("Link copied");
      back();
    } catch {
      setShown("link");
    }
  };

  return (
    <div ref={box} className={`row-menu${shown || note ? " shown" : ""}`}>
      <span role="status" className="row-note">
        {note}
      </span>
      <button
        ref={more}
        type="button"
        className="icon-button"
        aria-label={`Actions for ${name}`}
        aria-haspopup="menu"
        aria-expanded={shown === "menu"}
        onClick={() => setShown(shown === "menu" ? null : "menu")}
      >
        <span aria-hidden="true">⋯</span>
      </button>
      {shown === "menu" && (
        <Menu
          label={name}
          style={below}
          items={[
            { label: "Copy link", onSelect: () => void copy() },
            { label: "Open in new tab", href: sessionPath(name) },
          ]}
          onClose={back}
        />
      )}
      {shown === "link" && <LinkField name={name} link={link} style={below} onClose={back} />}
    </div>
  );
}

function LinkField({
  name,
  link,
  style,
  onClose,
}: {
  name: string;
  link: string;
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
      aria-label={`Link to ${name}`}
      className="popover link-popover"
      style={style}
      onKeyDown={(event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        onClose();
      }}
    >
      <input ref={field} type="text" readOnly aria-label="Link" value={link} />
      <p className="muted">Press ⌘C / Ctrl+C to copy</p>
    </div>
  );
}
