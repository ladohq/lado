// A kit's card in the lists of the Kits page (docs/design/ui.md, Kits: Card): its mark,
// name and version, the description cut to two lines, the source as a dot with its text, the
// counts and the address; the actions on the right. Installed and Available rows both use it.
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";

// The dot's colour follows the kind of source; its text always says which one.
export type SourceKind = "official" | "marketplace" | "git" | "folder" | "built-in";

export type Source = { label: string; kind: SourceKind };

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
  badges?: ReactNode;
  description: string | null;
  problem?: string | null;
  source: Source;
  agents: number;
  skills: number;
  flows: number;
  // A git address (shown short, the full one on hover) or a folder (as it is).
  address?: string | null;
  folder?: string | null;
  actions?: ReactNode;
}) {
  return (
    <li className="kit-row" aria-label={props.name}>
      <span className={`kit-mark${props.builtIn ? " built-in" : ""}`} aria-hidden="true">
        {initials(props.name)}
      </span>
      <div className="kit-body">
        <div className="kit-title">
          <span className="kit-name">{props.name}</span>
          {props.version && <span className="kit-version">{props.version}</span>}
          {props.badges}
        </div>
        {props.description && <Description text={props.description} />}
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
          {props.address && (
            <span className="kit-where" title={props.address}>
              {shortAddress(props.address)}
            </span>
          )}
          {!props.address && props.folder && <span className="kit-where">{props.folder}</span>}
        </div>
      </div>
      {props.actions && <div className="kit-actions">{props.actions}</div>}
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
