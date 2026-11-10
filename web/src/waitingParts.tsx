// The parts of a tab of the waiting card (docs/design/ui.md, The waiting card), shared by an
// agent's tab (WaitingCard.tsx), a gate's (GateCard.tsx) and a gate on its run's page: the
// question in a filled head on one line, the report, which alone scrolls, the
// recommendation's splitter, and the footer, always whole. A box that scrolls says there is
// more by a fade at its lower edge (useMore). A whole card (Needs you, a run's page) scrolls
// nothing inside: the page does.
import { useCallback, type ComponentProps, type ReactElement, type ReactNode } from "react";

import { MOST_LINES } from "./fieldHeight";
import { AlertIcon } from "./icons";
import { useAttempt, useLive, useLiveStore } from "./live";
import { REC_MIN } from "./prefs";
import { Recommendation } from "./Recommendation";
import { Splitter, useHeight } from "./Splitter";
import { Tooltip } from "./Tooltip";
import { useClamped, useMore } from "./useMore";

export const STOPPED_NOTE = "The session is stopped: resume it to answer.";
export const WAITING_NOTE = "Waiting for connection";

// A button that waits while the connection is lost says why in a tooltip. On the span around
// it, as a disabled button gets no mouse events. `tip`: its own tooltip the rest of the time.
export function Waits({ tip, children }: { tip?: string; children: ReactElement<object> }) {
  const { lost } = useLive();
  if (lost) {
    return (
      <Tooltip tip={WAITING_NOTE}>
        <span className="lost-wait" tabIndex={0}>
          {children}
        </span>
      </Tooltip>
    );
  }
  return tip === undefined ? children : <Tooltip tip={tip}>{children}</Tooltip>;
}

// An action without an answer, under its buttons (attempts.ts): what LADO knows of it in two
// words and Retry, on once LADO knows it did not arrive and the action can be sent; a Retry
// the server refused, as any refusal. `off`: the action's buttons are off for another reason.
export function ActionProblem({ attempt: key, off = false }: { attempt: string; off?: boolean }) {
  const live = useLiveStore();
  const { lost } = useLive();
  const attempt = useAttempt(key);
  if (attempt === undefined) return null;
  if (typeof attempt.state === "object") {
    return (
      <p className="field-problem" role="alert">
        {attempt.state.refused}
      </p>
    );
  }
  const missed = attempt.state === "missed";
  return (
    <div className="action-problem" role="alert">
      <AlertIcon />
      <b>{`${attempt.what} not ${missed ? "delivered" : "confirmed"}`}</b>
      <button type="button" className="quiet" disabled={!missed || lost || off} onClick={() => void live.attempts.retry(key)}>
        Retry
      </button>
    </div>
  );
}

// Choices in the footer, a question's or a choice gate's: by content up to their limit, then
// they scroll inside with a fade, a group the keyboard reaches.
export function ChoicesFrame({ children }: { children: ReactNode }) {
  const { box, more, scrolled } = useMore<HTMLDivElement>();
  return (
    <div className={`waiting-choices-frame${more ? " cut" : ""}`}>
      <div
        ref={box}
        className="waiting-choices"
        role="group"
        aria-label="Choices"
        tabIndex={more ? 0 : undefined}
        onScroll={scrolled}
      >
        {children}
      </div>
    </div>
  );
}

// A field's least and most lines in the card: it opens on one line.
export const CARD_FIELD_LINES: [number, number] = [1, MOST_LINES];

const REPORT_MIN = 56; // the report's least height (styles.css, .waiting-scroll)
const REC_LINES = { window: 82, phone: 42 }; // the recommendation's text by default: 4 lines, a phone's 2
const DRAG_MIN = 2; // a text less than this over REC_MIN, a line's rounding, has nothing to drag

// What a tab takes from its card.
export type CardShape = {
  whole: boolean; // Needs you, a run's page: nothing scrolls inside, nothing fades, no splitter
  chat: boolean; // in a session's chat: the recommendation has its splitter
  phone: boolean;
  fieldLines: [number, number]; // the lines a field opens with and grows to
  headId: string; // the head's, which names the panel
  feedRoom: number | null; // what the chat's feed can give over its least (null: not measured; Infinity: expanded, no feed)
  recHeight: number | null; // the recommendation's text, by its splitter (null: the default)
  setRecHeight: (height: number | null) => void;
  head: (element: HTMLElement | null) => void; // measured: the human's height leaves it whole
  foot: (element: HTMLElement | null) => void; // the same
};

// The question in the head, on one line; cut, the whole of it in a tooltip (a hover, the
// keyboard's focus, a tap) and the head a stop of the Tab key. A run's page puts its kicker over it.
function CardHead({
  card,
  title,
  kicker,
  item,
  marked,
  area,
}: {
  card: CardShape;
  title: string;
  kicker?: string;
  item?: number;
  marked: boolean;
  area?: Record<string, string>;
}) {
  const { text, clamped } = useClamped<HTMLHeadingElement>();
  return (
    <div ref={card.head} className={`waiting-head${marked ? " marked" : ""}`} data-item={item} {...area}>
      {kicker && <span className="waiting-kicker">{kicker}</span>}
      <Tooltip tip={clamped ? title : null}>
        <h3 ref={text} id={card.headId} className="waiting-head-text" tabIndex={clamped ? 0 : undefined}>
          {title}
        </h3>
      </Tooltip>
    </div>
  );
}

// The report: the one part that scrolls, a region the keyboard reaches, fading at its lower
// edge while more is below; whole, in the page's flow.
function CardReport({
  card,
  measured,
  area,
  children,
}: {
  card: CardShape;
  measured: (element: HTMLElement | null) => void;
  area?: Record<string, string>;
  children: ReactNode;
}) {
  const { box, more, scrolled } = useMore<HTMLDivElement>();
  const ref = useCallback(
    (element: HTMLDivElement | null) => {
      box.current = element;
      measured(element);
    },
    [box, measured],
  );
  return (
    <div
      ref={ref}
      className={`waiting-scroll${more && !card.whole ? " has-more" : ""}`}
      role="region"
      aria-label="Context of the card"
      tabIndex={card.whole ? undefined : 0}
      onScroll={scrolled}
      {...area}
    >
      <div className="waiting-scroll-body">{children}</div>
    </div>
  );
}

type RecProps = Omit<ComponentProps<typeof Recommendation>, "whole" | "height" | "text">;

// A tab of one item: its head (`title`; none for a tab of several questions), its report
// (`report`, null for none), then in the footer its recommendation (`rec`) and the rest
// (`children`). In a session's chat a given recommendation has a splitter over the footer,
// which sets its text's height between a line and the lesser of its whole text and the room
// the report gives down to its least and the feed down to its own; when its text is a line,
// nothing to drag, and elsewhere, a line parts the report from the footer.
export function CardBody({
  card,
  title,
  kicker,
  item,
  marked = false,
  area,
  report,
  rec,
  children,
}: {
  card: CardShape;
  title?: string;
  kicker?: string;
  item?: number; // what a link to an item scrolls to and marks
  marked?: boolean;
  area?: Record<string, string>; // the selection bar's (quote.ts)
  report: ReactNode;
  rec?: RecProps;
  children: ReactNode;
}) {
  const [textMeasured, textHeight] = useHeight<HTMLElement>();
  const [boxMeasured, boxHeight] = useHeight<HTMLElement>();
  const [reportMeasured, reportHeight] = useHeight<HTMLElement>();
  const given = card.chat && !card.whole && rec?.rec?.state === "given";
  const initial = card.phone ? REC_LINES.phone : REC_LINES.window;
  const asked = card.recHeight ?? initial;
  const full = textHeight ?? Infinity; // not laid out yet: the height asked
  // The room the text and the report share, less the report's least, and what the feed can
  // give past it: the card grows into the feed once the report is at its least.
  const fromReport = report ? (reportHeight === null ? null : Math.max(0, reportHeight - REPORT_MIN)) : 0;
  // The feed not measured gives nothing; an expanded card has none (Infinity), and its report,
  // which fills the card, is then the room the text takes from.
  const feed = card.feedRoom ?? 0;
  const fromFeed = report && !Number.isFinite(feed) ? 0 : Math.max(0, feed);
  const room = boxHeight !== null && fromReport !== null ? boxHeight + fromReport + fromFeed : Infinity; // not laid out yet
  const most = Math.min(full, room);
  const max = Math.max(REC_MIN, Math.floor(Number.isFinite(most) ? most : asked));
  const height = card.recHeight === null ? null : Math.max(REC_MIN, Math.min(card.recHeight, max));
  // A text of a line has nothing to drag. Only the text's height counts: the room changes as
  // the splitter comes and goes, which would make it flicker.
  const split = given && full - REC_MIN >= DRAG_MIN;
  return (
    <>
      {title !== undefined && (
        <CardHead card={card} title={title} kicker={kicker} item={item} marked={marked} area={area} />
      )}
      {report && (
        <CardReport card={card} measured={reportMeasured} area={title === undefined ? undefined : area}>
          {report}
        </CardReport>
      )}
      {split && (
        <Splitter
          label="Resize the recommendation"
          edge="top"
          width={Math.round(height ?? Math.min(initial, max))}
          bounds={{ initial, min: REC_MIN, max }}
          onChange={(next) => card.setRecHeight(next)}
          onReset={() => card.setRecHeight(null)}
          grip
          hint={false}
        />
      )}
      <div ref={card.foot} className={`waiting-foot${split || !report ? "" : " ruled"}`}>
        {rec && <Recommendation {...rec} whole={card.whole} height={height} measure={{ text: textMeasured, box: boxMeasured }} />}
        {children}
      </div>
    </>
  );
}
