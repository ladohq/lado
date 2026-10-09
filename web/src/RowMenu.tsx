// The ⋯ of a list row or a card (docs/design/ui.md, Launch and session control; Kits:
// Card): the session list's rows (SessionRowMenu.tsx) and the Kits page's cards. A button
// opens the shared Menu.tsx below it; the focus goes back to ⋯ when it closes. A copy item
// copies through Copy.tsx: what was copied is said in the row, outside the menu, which
// closes; when copying fails, the text is shown selected. The CSS shows ⋯ on its row's
// hover and focus, while open or while its note shows, and always on a device without hover.
import { useRef, useState } from "react";

import { CopyField, useCopy } from "./Copy";
import { Menu, useBelow, useDismiss, type MenuItem } from "./Menu";

export type CopyItem = {
  label: string; // "Copy link"
  copy: string; // the text
  copied: string; // "Link copied"
  field: { title: string; label: string }; // the field it is shown in when copying fails
};

export type RowMenuItem = MenuItem | CopyItem;

export function RowMenu({ name, items }: { name: string; items: RowMenuItem[] }) {
  const [shown, setShown] = useState<"menu" | CopyItem | null>(null);
  const { note, copy } = useCopy();
  const box = useRef<HTMLDivElement>(null);
  const more = useRef<HTMLButtonElement>(null);
  const popover = useRef<HTMLDivElement>(null); // the menu, or the text to copy
  const close = () => setShown(null);
  useDismiss(shown !== null, box, close);
  const below = useBelow(box, popover, shown !== null);

  const back = () => {
    close();
    more.current?.focus();
  };
  const copyOf = (item: CopyItem) => async () => {
    if (await copy(item.copy, item.copied)) back();
    else setShown(item);
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
          ref={popover}
          style={below}
          items={items.map((item) => ("copy" in item ? { label: item.label, onSelect: () => void copyOf(item)() } : item))}
          onClose={back}
        />
      )}
      {shown !== null && shown !== "menu" && (
        <CopyField
          title={shown.field.title}
          label={shown.field.label}
          text={shown.copy}
          ref={popover}
          style={below}
          onClose={back}
        />
      )}
    </div>
  );
}
