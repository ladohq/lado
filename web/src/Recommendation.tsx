// The lead's recommendation on a gate or on another agent's question to the human
// (docs/design/ui.md, The supervisor's recommendation; lado.runtime.recommend): part of the
// card, never an entry of its own. Open, one block in every place the card stands (the chat,
// Needs you, a run's page): who recommends what, then its text in a box the splitter above
// the card's footer sets the height of (waitingParts.tsx); the recommended option is a gate's
// one primary button (primaryOf), and a question's choice picked ahead in its tab
// (WaitingCard.tsx); closed, one quiet line whose text opens on a click. The human answers in
// every state: nothing waits for it.
import { useCallback, type CSSProperties } from "react";

import type { RecommendationInfo } from "./api";
import { Body, clock } from "./ChatText";
import { MiniAvatar } from "./FeedRow";
import { AlertIcon } from "./icons";
import { Tooltip } from "./Tooltip";
import { useMore } from "./useMore";

export const LEAD = "supervisor";
const TITLE = "Supervisor's recommendation";
const ASKED = "Supervisor is preparing a recommendation…";

// The option a card makes its primary button: the recommended one when it is one of
// `options`, else the first, as without a recommendation.
export function primaryOf(options: string[], rec?: RecommendationInfo | null): string | undefined {
  const chosen = rec?.state === "given" ? rec.choice : null;
  return chosen && options.includes(chosen) ? chosen : options[0];
}

export const disagreed = (rec: RecommendationInfo, verb: string) => `${verb}${rec.by ? ` with ${rec.by}` : ""}`;

// An open card's block: "supervisor recommends <option>" as the card's buttons name it (a
// choice not among `options` counts as none, as in primaryOf), the time, then the text in its
// box, `height` high (null: the stylesheet's 4 lines, a phone's 2) and fading at its lower
// edge while more is below; `whole`, all of it. A disagreement is a --warn frame and a sign,
// its words in the block's name and the sign's tooltip; none when the lead wrote the gate's
// report itself. While it is asked, one muted line; missing or never asked, nothing.
export function Recommendation({
  rec,
  options,
  label = (option) => option,
  kind,
  whole = false,
  height = null,
  measure,
  area,
}: {
  rec?: RecommendationInfo | null;
  options: string[];
  label?: (option: string) => string;
  kind: "gate" | "question";
  whole?: boolean;
  height?: number | null;
  // The whole text and the box that shows it, for the card's splitter.
  measure?: { text: (element: HTMLElement | null) => void; box: (element: HTMLElement | null) => void };
  area?: Record<string, string>; // the selection bar's (quote.ts)
}) {
  if (!rec || rec.state === "missing") return null;
  if (rec.state === "asked") return <p className="rec-asked">{ASKED}</p>;
  const option = rec.choice && options.includes(rec.choice) ? label(rec.choice) : null;
  const against = rec.disagrees && rec.by !== LEAD;
  const name = against ? `${TITLE}, disagrees with ${kind === "gate" ? "the step's report" : (rec.by ?? "the agent")}` : TITLE;
  return (
    <section className={`rec${against ? " against" : ""}`} role="note" aria-label={name} {...area}>
      <div className="rec-head">
        {against && (
          <Tooltip tip={name}>
            <span className="rec-warn">
              <AlertIcon />
            </span>
          </Tooltip>
        )}
        <MiniAvatar who={LEAD} />
        <span className="rec-title">
          {option ? (
            <>
              supervisor recommends <b>{option}</b>
            </>
          ) : (
            "supervisor"
          )}
        </span>
        {rec.at && <time dateTime={rec.at}>{clock(rec.at)}</time>}
      </div>
      <RecText text={rec.text} whole={whole} height={height} measure={measure} />
    </section>
  );
}

// The text in its box: it scrolls on its own, the keyboard reaches it, a fade says there is more.
function RecText({
  text,
  whole,
  height,
  measure,
}: {
  text: string;
  whole: boolean;
  height: number | null;
  measure?: { text: (element: HTMLElement | null) => void; box: (element: HTMLElement | null) => void };
}) {
  const { box, more, scrolled } = useMore<HTMLDivElement>();
  const measured = measure?.box;
  const ref = useCallback(
    (element: HTMLDivElement | null) => {
      box.current = element;
      measured?.(element);
    },
    [box, measured],
  );
  const style = height !== null && !whole ? ({ "--adv": `${height}px` } as CSSProperties) : undefined;
  return (
    <div
      ref={ref}
      className={`rec-text${more && !whole ? " has-more" : ""}`}
      tabIndex={whole ? undefined : 0}
      style={style}
      onScroll={scrolled}
    >
      <div ref={measure?.text} className="rec-text-body">
        <Body text={text} />
      </div>
    </div>
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
