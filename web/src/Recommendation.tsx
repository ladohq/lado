// The lead's recommendation on a gate or on another agent's question to the human
// (docs/design/ui.md, Flow gates and A question; lado.runtime.recommend): part of the card,
// never an entry of its own. Open, a block between the question's text and the answer on a
// run's page, and one line over the answer in the waiting card (RecommendationBar); the
// recommended option is a gate's one primary button (primaryOf), and a question's choice
// picked ahead in its tab (WaitingCard.tsx); closed, one quiet line whose text opens on a
// click. The human answers in every state: nothing waits for it.
import { useState, type CSSProperties } from "react";

import type { RecommendationInfo } from "./api";
import { Body, clock } from "./ChatText";
import { avatar, MiniAvatar } from "./FeedRow";
import { Tooltip } from "./Tooltip";
import { useMore } from "./waitingParts";

const LEAD = "supervisor";
const TITLE = "Supervisor's recommendation";
const WAITING = { asked: "Supervisor is preparing a recommendation…", missing: "The supervisor gave no recommendation" };

// The option a card makes its primary button: the recommended one when it is one of
// `options`, else the first, as without a recommendation.
export function primaryOf(options: string[], rec?: RecommendationInfo | null): string | undefined {
  const chosen = rec?.state === "given" ? rec.choice : null;
  return chosen && options.includes(chosen) ? chosen : options[0];
}

export const disagreed = (rec: RecommendationInfo, verb: string) => `${verb}${rec.by ? ` with ${rec.by}` : ""}`;

// An open card's block: the supervisor's avatar and the title, "disagrees with <agent>" in
// orange when the lead disagrees, the time, the whole text. While it is asked, or when the
// lead's turn ended without it, one muted line says so; none asked, nothing.
export function Recommendation({ rec }: { rec?: RecommendationInfo | null }) {
  if (!rec) return null;
  if (rec.state !== "given") {
    return (
      <section className="rec waiting" aria-label={TITLE}>
        <div className="rec-head">
          <MiniAvatar who={LEAD} />
          <span className="rec-title">
            {WAITING[rec.state]}
          </span>
        </div>
      </section>
    );
  }
  // Its band is the supervisor's avatar colour; orange (.differs) when it disagrees.
  const band = { "--rec-band": `var(--avatar-${avatar(LEAD).colour})` } as CSSProperties;
  return (
    <section className={`rec${rec.disagrees ? " differs" : ""}`} aria-label={TITLE} style={band}>
      <div className="rec-head">
        <MiniAvatar who={LEAD} />
        <span className="rec-title">{TITLE}</span>
        {rec.disagrees && <span className="rec-differs">{disagreed(rec, "disagrees")}</span>}
        {rec.at && <time dateTime={rec.at}>{clock(rec.at)}</time>}
      </div>
      <Body text={rec.text} />
    </section>
  );
}

// Markdown's paired marks out of a text whose code stands aside. A mark counts only at a
// word's edge, so max_retries and 2*3 stay.
const unmarked = (text: string) =>
  text
    .replace(/(^|[^\w*])\*\*(\S(?:.*?\S)??)\*\*(?![\w*])/g, "$1$2")
    .replace(/(^|[^\w_])__(\S(?:.*?\S)??)__(?![\w_])/g, "$1$2")
    .replace(/(^|[^\w*])\*(\S(?:[^*]*\S)?)\*(?![\w*])/g, "$1$2")
    .replace(/(^|[^\w_])_(\S(?:[^_]*\S)?)_(?![\w_])/g, "$1$2")
    .replace(/~~(\S(?:.*?\S)??)~~/g, "$1");

const FENCE = /^ {0,3}(`{3,}|~{3,})[^`\n]*\n([\s\S]*?)(?:^ {0,3}\1[`~]*[ \t]*$|(?![\s\S]))/gm; // to its end, closed or not
const CODE = /(`+)([\s\S]+?)\1(?!`)/g;

// Markdown on one line: its links, line marks and paired marks out, its white space collapsed.
// Code stands aside meanwhile, so it stays as it is and a mark around it still finds its pair.
export const oneLine = (text: string) => {
  const code: string[] = [];
  const aside = (_: string, _mark: string, inner: string) => `\uE000${code.push(inner) - 1}\uE001`;
  const marked = text
    .replace(FENCE, aside)
    .replace(CODE, aside)
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/^\s{0,3}(#{1,6}|>|[-*+]|\d+\.)\s+/gm, "");
  return unmarked(marked)
    .replace(/\uE000(\d+)\uE001/g, (_, n: string) => code[Number(n)])
    .replace(/\s+/g, " ")
    .trim();
};

// The text under the line, in a box that scrolls: a fade at its lower edge says there is more.
function RecBody({ text }: { text: string }) {
  const { box, more, scrolled } = useMore<HTMLDivElement>();
  return (
    <div className={`rec-bar-frame${more ? " cut" : ""}`}>
      <div ref={box} className="rec-bar-body" tabIndex={0} onScroll={scrolled}>
        <Body text={text} />
      </div>
    </div>
  );
}

// The waiting card's line over the answer: the supervisor's avatar, "Supervisor recommends
// <option>:" as the card's buttons name it, the disagreement right after it so a cut never
// takes it, then the text cut on one line (a phone: two). Its whole text and time in the
// tooltip; a click opens the text to 3 lines that scroll; `whole`, in the expanded card, it
// shows all of it. A choice not among `options` counts as none, as in primaryOf.
export function RecommendationBar({
  rec,
  options,
  label = (option) => option,
  whole = false,
  area,
}: {
  rec?: RecommendationInfo | null;
  options: string[];
  label?: (option: string) => string;
  whole?: boolean;
  area?: Record<string, string>; // the selection bar's (quote.ts)
}) {
  const [opened, setOpened] = useState(false);
  if (!rec) return null;
  if (rec.state !== "given") {
    return (
      <section className="rec-bar waiting" aria-label={TITLE}>
        <span className="rec-bar-line">
          <MiniAvatar who={LEAD} />
          <span className="rec-bar-text">{WAITING[rec.state]}</span>
        </span>
      </section>
    );
  }
  const option = rec.choice && options.includes(rec.choice) ? label(rec.choice) : null;
  const name = (
    <b className="rec-bar-name">
      {option ? `Supervisor recommends ${option}` : TITLE}
      {rec.disagrees && <span className="rec-differs"> · {disagreed(rec, "disagrees")}</span>}:
    </b>
  );
  const body = <RecBody text={rec.text} />;
  const classes = `rec-bar${rec.disagrees ? " differs" : ""}${whole ? " whole" : ""}${opened && !whole ? " opened" : ""}`;
  if (whole) {
    return (
      <section className={classes} aria-label={TITLE} {...area}>
        <span className="rec-bar-line">
          <MiniAvatar who={LEAD} />
          {name}
        </span>
        {body}
      </section>
    );
  }
  return (
    <section className={classes} aria-label={TITLE} {...area}>
      <Tooltip tip={`${rec.text}${rec.at ? ` · ${clock(rec.at)}` : ""}`}>
        <button type="button" className="rec-bar-line" aria-expanded={opened} onClick={() => setOpened(!opened)}>
          <MiniAvatar who={LEAD} />
          <span className="rec-bar-cut">
            {name}
            {!opened && " "}
            {!opened && <span className="rec-bar-text">{oneLine(rec.text)}</span>}
          </span>
        </button>
      </Tooltip>
      {opened && body}
    </section>
  );
}

// A closed card's line: "Supervisor recommended: <option>" (as `label` names it on the
// card's buttons), or the title without an option; a disagreement in orange; the text on a
// click. Only a recommendation that was given.
export function RecommendationLine({
  rec,
  label = (option) => option,
}: {
  rec?: RecommendationInfo | null;
  label?: (option: string) => string;
}) {
  if (rec?.state !== "given") return null;
  return (
    <details className="rec-closed">
      <summary>
        <MiniAvatar who={LEAD} />
        {rec.choice ? `Supervisor recommended: ${label(rec.choice)}` : TITLE}
        {rec.disagrees && <span className="rec-closed-differs"> · {disagreed(rec, "disagreed")}</span>}
      </summary>
      <Body text={rec.text} />
    </details>
  );
}
