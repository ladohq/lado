// The parts of a tab of the waiting card (docs/design/ui.md, The waiting card), shared by an
// agent's tab (WaitingCard.tsx) and a gate's (GateCard.tsx): a title of at most two lines,
// the context, which alone scrolls, and the footer, always whole. A box that scrolls says
// there is more by a fade (useMore); the context adds "↓ more", the card's Expand.
import { useCallback, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from "react";

import { MOST_LINES } from "./fieldHeight";

export const STOPPED_NOTE = "The session is stopped: resume it to answer.";

const FIELD_LINES = 4; // the lines a card's field grows to, in the card not expanded

// A field's least and most lines in the card: it opens on one line.
export const cardLines = (expanded: boolean): [number, number] => [1, expanded ? MOST_LINES : FIELD_LINES];

// What a tab takes from its card.
export type CardShape = {
  expanded: boolean;
  more: () => void; // "↓ more": expands the card
  foot: (element: HTMLElement | null) => void; // measured: the human's height leaves it whole
};

// Runs `changed` now and whenever `box` or its first child is laid out anew.
function useLaidOut(box: RefObject<HTMLElement | null>, changed: () => void) {
  useLayoutEffect(changed); // a change of the content a render makes
  useLayoutEffect(() => {
    const element = box.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(changed);
    observer.observe(element);
    if (element.firstElementChild) observer.observe(element.firstElementChild);
    return () => observer.disconnect();
  }, [box, changed]);
}

// Whether a box that scrolls has more below what it shows, and the `scrolled` to call on its
// scroll. A pixel of slack: a zoomed page rounds the heights.
export function useMore<T extends HTMLElement>() {
  const box = useRef<T>(null);
  const [more, setMore] = useState(false);
  const scrolled = useCallback(() => {
    const element = box.current;
    if (element) setMore(element.scrollTop + element.clientHeight < element.scrollHeight - 1);
  }, []);
  useLaidOut(box, scrolled);
  return { box, more, scrolled };
}

// Whether a text its stylesheet clamps is cut.
function useClamped<T extends HTMLElement>() {
  const text = useRef<T>(null);
  const [clamped, setClamped] = useState(false);
  const measure = useCallback(() => {
    const element = text.current;
    if (element) setClamped(element.scrollHeight > element.clientHeight + 1);
  }, []);
  useLaidOut(text, measure);
  return { text, clamped };
}

// The context: the one part that scrolls, a region the keyboard reaches whether it overflows
// or not. The fade and "↓ more" lie outside the box that scrolls, so they stay at its edge.
function CardContext({ card, children }: { card: CardShape; children: ReactNode }) {
  const { box, more, scrolled } = useMore<HTMLDivElement>();
  const cut = more && !card.expanded;
  return (
    <div className={`waiting-context-frame${cut ? " cut" : ""}`}>
      <div ref={box} className="waiting-context" role="region" aria-label="Context of the card" tabIndex={0} onScroll={scrolled}>
        <div className="waiting-context-body">{children}</div>
      </div>
      {cut && (
        <button type="button" className="waiting-more" onClick={card.more}>
          ↓ more
        </button>
      )}
    </div>
  );
}

// The title with its meta, then the context; the whole text stands first in it when the
// title is cut. A tab of several questions has no title. `children` null: no context.
export function CardTop({
  card,
  title,
  meta,
  item,
  marked = false,
  area,
  children,
}: {
  card: CardShape;
  title?: string;
  meta?: string;
  item?: number; // what a link to an item scrolls to and marks
  marked?: boolean;
  area?: Record<string, string>; // the selection bar's (quote.ts)
  children: ReactNode;
}) {
  const { text, clamped } = useClamped<HTMLHeadingElement>();
  const whole = title !== undefined && clamped ? <p className="waiting-whole">{title}</p> : null;
  return (
    <div className={`waiting-top${marked ? " marked" : ""}`} data-item={item} {...area}>
      {title !== undefined && (
        <div className="waiting-title">
          <h4 ref={text} className="waiting-title-text">
            {title}
          </h4>
          <span className="waiting-meta">{meta}</span>
        </div>
      )}
      {(whole || children) && (
        <CardContext card={card}>
          {whole}
          {children}
        </CardContext>
      )}
    </div>
  );
}

export function CardFoot({ card, children }: { card: CardShape; children: ReactNode }) {
  return (
    <div ref={card.foot} className="waiting-foot">
      {children}
    </div>
  );
}
