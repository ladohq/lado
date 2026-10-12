// The lead's recommendation on a gate or on another agent's question to the human
// (docs/design/ui.md, Flow gates and A question; lado.runtime.recommend): part of the card,
// never an entry of its own. Open, a block between the question's text and the answer, and
// the recommended option is the card's one primary button (primaryOf); closed, one quiet
// line whose text opens on a click. The human answers in every state: nothing waits for it.
import type { CSSProperties } from "react";

import type { RecommendationInfo } from "./api";
import { Body, clock } from "./ChatText";
import { avatar, MiniAvatar } from "./FeedRow";

const LEAD = "supervisor";
const TITLE = "Supervisor's recommendation";

// The option a card makes its primary button: the recommended one when it is one of
// `options`, else the first, as without a recommendation.
export function primaryOf(options: string[], rec?: RecommendationInfo | null): string | undefined {
  const chosen = rec?.state === "given" ? rec.choice : null;
  return chosen && options.includes(chosen) ? chosen : options[0];
}

const disagreed = (rec: RecommendationInfo, verb: string) => `${verb}${rec.by ? ` with ${rec.by}` : ""}`;

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
            {rec.state === "asked" ? "Supervisor is preparing a recommendation…" : "The supervisor gave no recommendation"}
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
