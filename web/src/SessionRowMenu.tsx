// A session list row's menu (docs/design/ui.md, Launch and session control): actions on the
// entry only, and only ones that work: Copy link and Open in new tab. The session's own
// actions are in its head (SessionControl.tsx). The link is the page's address without the
// token: the login is the browser's cookie. Copying is Copy.tsx's: when it fails, the
// address is shown selected; "Link copied" is said in the row, outside the menu, which
// closes.
import { useRef, useState } from "react";

import { CopyField, useCopy } from "./Copy";
import { Menu, useBelow, useDismiss } from "./Menu";
import { sessionLink, sessionPath } from "./paths";

export function SessionRowMenu({ name }: { name: string }) {
  const [shown, setShown] = useState<"menu" | "link" | null>(null);
  const { note, copy } = useCopy();
  const box = useRef<HTMLDivElement>(null);
  const more = useRef<HTMLButtonElement>(null);
  const close = () => setShown(null);
  useDismiss(shown !== null, box, close);
  const below = useBelow(box, shown !== null);
  const link = sessionLink(name);

  const back = () => {
    close();
    more.current?.focus();
  };
  const copyLink = async () => {
    if (await copy(link, "Link copied")) back();
    else setShown("link");
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
            { label: "Copy link", onSelect: () => void copyLink() },
            { label: "Open in new tab", href: sessionPath(name) },
          ]}
          onClose={back}
        />
      )}
      {shown === "link" && <CopyField title={`Link to ${name}`} label="Link" text={link} style={below} onClose={back} />}
    </div>
  );
}