// A kit's card in the grids of the Kits page (docs/design/ui.md, Kits: Card): its mark, its
// name on one line (the whole name and its address or folder in its title), the version line
// with the card's one action and the badges, the description cut to two lines, the problem,
// and the source as a dot with its text and the counts; ⋯ in the corner. Installed and
// Available cards both use it.
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";

import { RowMenu, type RowMenuItem } from "./RowMenu";

// The dot's colour follows the kind of source; its text always says which one.
export type SourceKind = "official" | "marketplace" | "git" | "folder" | "built-in";

export type Source = { label: string; kind: SourceKind };

// The action by the version: ↑ to the newer version `to` a check found (Update, U2), or +
// (Install, AV1); `label` is the button's name and title.
export type CardAction = { symbol: "↑" | "+"; label: string; to?: string; onSelect: () => void };

// "lado-dev" → "LD": the first letters of the first two parts, else the first two letters.
export function initials(name: string): string {
  const parts = name.split(/[-_]/).filter(Boolean);
  const letters = parts.length >= 2 ? parts[0][0] + parts[1][0] : name.slice(0, 2);
  return letters.toUpperCase();
}

// A git address without its scheme, its user and ".git": "github.com/acme/kit";
// "git@host:path" becomes "host/path".
export function shortAddress(address: string): string {
  return address
    .replace(/^[a-z][a-z0-9+.-]*:\/\//i, "")
    .replace(/^[^@/]+@/, "")
    .replace(/^([^/:]+):(?!\d)/, "$1/")
    .replace(/\.git$/, "");
}

export function KitCard(props: {
  name: string;
  builtIn?: boolean;
  version: string | null;
  action?: CardAction;
  badges?: ReactNode;
  description: string | null;
  // Said in muted italics when there is no description.
  noDescription?: string;
  problem?: string | null;
  source: Source;
  agents: number;
  skills: number;
  flows: number;
  // A git address or a folder: in the name's title, and copied from ⋯.
  where?: string | null;
  menu?: RowMenuItem[];
}) {
  const { action } = props;
  return (
    <li className="kit-card" aria-label={props.name}>
      <div className="kit-top">
        <span className={`kit-mark${props.builtIn ? " built-in" : ""}`} aria-hidden="true">
          {initials(props.name)}
        </span>
        <div className="kit-title">
          <span className="kit-name" title={[props.name, props.where].filter(Boolean).join("\n")}>
            {props.name}
          </span>
          <div className="kit-version-line">
            {props.version && <span className="kit-version">{props.version}</span>}
            {action?.to && (
              <>
                <span className="kit-arrow" aria-hidden="true">
                  →
                </span>
                <span className="kit-version kit-newer">{action.to}</span>
              </>
            )}
            {action && (
              <button
                type="button"
                className="kit-action"
                aria-label={action.label}
                title={action.label}
                onClick={action.onSelect}
              >
                {action.symbol}
              </button>
            )}
            {props.badges}
          </div>
        </div>
      </div>
      {props.description ? (
        <Description text={props.description} />
      ) : (
        props.noDescription && <p className="kit-description kit-no-description">{props.noDescription}</p>
      )}
      {props.problem && (
        <p className="kit-problem" role="alert">
          {props.problem}
        </p>
      )}
      <div className="kit-meta">
        <span className="kit-source" data-source={props.source.kind}>
          {props.source.label}
        </span>
        <Counts agents={props.agents} skills={props.skills} flows={props.flows} />
      </div>
      {props.menu && <RowMenu name={props.name} items={props.menu} />}
    </li>
  );
}

const noun = (count: number, word: string) => `${word}${count === 1 ? "" : "s"}`;

// "4 roles 71 skills 2 flows", the number first and bold, leaving out what it has none of.
function Counts({ agents, skills, flows }: { agents: number; skills: number; flows: number }) {
  const parts = ([
    [agents, "role"],
    [skills, "skill"],
    [flows, "flow"],
  ] as const).filter(([count]) => count > 0);
  if (parts.length === 0) return null;
  return (
    <span className="kit-counts" aria-label={parts.map(([count, word]) => `${count} ${noun(count, word)}`).join(", ")}>
      {parts.map(([count, word]) => (
        <span key={word} aria-hidden="true">
          <b>{count}</b> {noun(count, word)}
        </span>
      ))}
    </span>
  );
}

// The description in two lines; "more" only when CSS cut it, measured again on a resize.
function Description({ text }: { text: string }) {
  const paragraph = useRef<HTMLParagraphElement>(null);
  const [open, setOpen] = useState(false);
  const [cut, setCut] = useState(false);
  useLayoutEffect(() => {
    const element = paragraph.current;
    if (!element || open) return;
    const measure = () => setCut(element.scrollHeight > element.clientHeight + 1);
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [open, text]);
  return (
    <div className="kit-description-box">
      <p ref={paragraph} className={`kit-description${open ? "" : " clamped"}`} title={text}>
        {text}
      </p>
      {(cut || open) && (
        <button type="button" className="link-button kit-more" onClick={() => setOpen(!open)}>
          {open ? "less" : "more"}
        </button>
      )}
    </div>
  );
}
