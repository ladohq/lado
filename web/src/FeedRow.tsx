// A row of a session's feed (docs/design/ui.md, The human in the session): the avatar, the
// head (who, a muted part, the time) and what the row holds. The one place that draws who
// wrote an entry, in the chat and on Needs you; a question's, a gate's or a message's own
// content comes as children. A row that continues a group (Chat.tsx, feedRows) has no head
// and no letter; its time stands where the avatar would.
import type { ReactNode } from "react";

import { clock } from "./ChatText";
import { GateIcon } from "./icons";

// The avatars' colours, --avatar-1 … --avatar-6 in tokens.css.
export const AVATAR_COLOURS = 6;

// A name's avatar: its first letter, capital, and a colour from the name alone (FNV-1a), so
// an agent keeps its colour on every page. Roles of one letter differ only by colour.
export function avatar(name: string): { letter: string; colour: number } {
  let hash = 0x811c9dc5;
  for (const char of name) hash = Math.imul(hash ^ char.codePointAt(0)!, 0x01000193) >>> 0;
  return { letter: (Array.from(name)[0] ?? "?").toUpperCase(), colour: (hash % AVATAR_COLOURS) + 1 };
}

// Whose row: an agent's (by its name), the human's (its own ground) or a flow gate's.
export type RowKind = "agent" | "human" | "gate";

function Avatar({ kind, who }: { kind: RowKind; who: string }) {
  if (kind === "gate") {
    return (
      <span className="avatar avatar-gate" aria-hidden="true">
        <GateIcon />
      </span>
    );
  }
  if (kind === "human") {
    return (
      <span className="avatar avatar-human" aria-hidden="true">
        Y
      </span>
    );
  }
  const { letter, colour } = avatar(who);
  return (
    <span className={`avatar avatar-${colour}`} aria-hidden="true">
      {letter}
    </span>
  );
}

export function FeedRow({
  kind,
  who,
  aside,
  at,
  continued = false,
  label,
  id,
  className = "",
  children,
}: {
  kind: RowKind;
  who: string;
  aside?: ReactNode;
  at: string;
  continued?: boolean;
  label: string;
  id?: string;
  className?: string;
  children: ReactNode;
}) {
  const time = <time dateTime={at}>{clock(at)}</time>;
  const classes = ["feed-row", kind === "human" && "mine", continued && "continued", className].filter(Boolean);
  return (
    <article className={classes.join(" ")} id={id} aria-label={label}>
      <div className="feed-side">{continued ? time : <Avatar kind={kind} who={who} />}</div>
      <div className="feed-main">
        {!continued && (
          <header className="feed-head">
            <span className="feed-who">{who}</span>
            {aside && <span className="feed-aside">{aside}</span>}
            {time}
          </header>
        )}
        {children}
      </div>
    </article>
  );
}
