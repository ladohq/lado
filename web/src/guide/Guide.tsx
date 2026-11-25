// The first-run guide's engine (docs/design/ui.md, First-run guide): it reads the hints of
// hints.ts, decides which one shows (conditions.ts), draws it over the unchanged UI and keeps
// its marks on the server (POST /api/guide). A lazy chunk: mount.tsx loads it only while
// something is left to show, or after Help → Getting started.
//
// A guiding step dims the page, cuts its target out of the dim (presses there reach the page,
// presses on the dim do nothing), rings it and stands its card beside it (place.ts); it moves
// on only when what it waits for happens (the next step's condition holds). A step whose
// target is in a window of the app (the login sheet, a <dialog>) draws no dim of its own: the
// window's backdrop is the dim. Another window over a step hides the guide until it closes. A
// tip has no dim, takes no focus and blocks nothing. A hint is marked shown as it appears; a
// hint whose marker is not on screen for 2 s is skipped for the page load and journaled.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useLocation } from "react-router";

import { postGuide, type GuideInfo } from "../api";
import { findMarker, holds, partDone, visible, type Context } from "./conditions";
import { currentFacts, subscribe } from "./facts";
import { HINTS, PARTS, type Hint, type Part, type Texts } from "./hints";
import { place, PAD, type Placement, type Rect } from "./place";

export const MISSING_MS = 2000; // how long a hint waits for its marker
const RING_OUT = 3; // the pointing ring outside its target

type Props = {
  info: GuideInfo;
  restarted: boolean; // Help → Getting started in this page load
  onInfo: (info: GuideInfo) => void;
};

type Shown =
  | { mode: "none" }
  | { mode: "hidden" } // a step waits behind another window
  | { mode: "missing"; hint: Hint }
  | { mode: "centred"; hint: Hint }
  | { mode: "step"; hint: Hint; target: HTMLElement; anchor: HTMLElement | null; inWindow: HTMLElement | null }
  | { mode: "tip"; hint: Hint; target: HTMLElement; inWindow: HTMLElement | null };

// The windows of the app that are open: modal <dialog>s and dialogs of its own (the login
// sheet, the login window).
function openWindows(): HTMLElement[] {
  const found = [
    ...document.querySelectorAll<HTMLElement>("dialog[open]"),
    ...document.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]'),
  ];
  return found.filter((one) => !one.closest(".gd-layer") && visible(one));
}

const windowOf = (element: HTMLElement) =>
  element.closest<HTMLElement>("dialog[open], .login-sheet, [role='dialog'][aria-modal='true']");

const rectOf = (element: Element): Rect => {
  const box = element.getBoundingClientRect();
  return { x: box.left, y: box.top, w: box.width, h: box.height };
};

const FOCUSABLE = "a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select, [tabindex]:not([tabindex='-1'])";

// A paragraph's **names** in bold and `code` as code.
function Rich({ text }: { text: string }) {
  const parts: ReactNode[] = [];
  const pattern = /\*\*(.+?)\*\*|`(.+?)`/g;
  let at = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > at) parts.push(text.slice(at, match.index));
    parts.push(match[1] !== undefined ? <b key={match.index}>{match[1]}</b> : <code key={match.index}>{match[2]}</code>);
    at = match.index + match[0].length;
  }
  if (at < text.length) parts.push(text.slice(at));
  return <>{parts}</>;
}

const plainText = (text: string) => text.replace(/\*\*(.+?)\*\*/g, "$1").replace(/`(.+?)`/g, "$1");

function accessibleName(element: HTMLElement): string {
  const label = element.getAttribute("aria-label");
  if (label) return label;
  const labelled = element.getAttribute("aria-labelledby");
  const by = labelled ? document.getElementById(labelled)?.textContent : null;
  return (by ?? element.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 80);
}

export default function Guide({ info, restarted, onInfo }: Props) {
  const { pathname } = useLocation();
  const [, setTick] = useState(0);
  const layer = useRef<HTMLDivElement>(null);
  const frame = useRef(0);
  const refresh = useCallback(() => {
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => setTick((n) => n + 1));
  }, []);

  // This page load's state of the guide.
  const [closed, setClosed] = useState(false); // Not now, Esc
  const [welcomed, setWelcomed] = useState(false); // Show me, or no welcome due
  const [passed, setPassed] = useState<ReadonlySet<string>>(new Set());
  const [noneOfThese, setNoneOfThese] = useState(false);
  const [skipped, setSkipped] = useState<ReadonlySet<string>>(new Set());
  const [tip, setTip] = useState<string | null>(null); // the tip shown now
  const [tipsDone, setTipsDone] = useState<ReadonlySet<string>>(new Set()); // Got it, or left
  const marked = useRef(new Set<string>());
  const atStart = useRef<Set<Part> | null>(null); // the parts left when the guide started
  const doneNow = useRef(new Set<Part>()); // the parts done during this run of the guide
  const closedSheet = useRef<string | null>(null); // a login window that closed, to judge
  const focusBefore = useRef<Element | null>(null);
  const lastTarget = useRef<HTMLElement | null>(null);

  const mark = useCallback(
    (action: Parameters<typeof postGuide>[0]) => {
      postGuide(action).then(onInfo, () => {}); // a mark that fails is shown again next time
    },
    [onInfo],
  );

  // What changes what shows: the page's markers (not the guide's own), the facts the
  // Settings pages publish, the window's size and any scroll.
  useEffect(() => {
    const observer = new MutationObserver((records) => {
      if (records.some((record) => !layer.current?.contains(record.target))) refresh();
    });
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["data-guide", "data-guide-cli", "data-guide-choice", "data-guide-picked", "data-guide-refusal", "hidden", "open", "data-open", "data-phone", "aria-modal"],
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-phone"] });
    const off = subscribe(refresh);
    window.addEventListener("resize", refresh);
    window.addEventListener("scroll", refresh, true);
    void document.fonts?.ready.then(refresh);
    refresh(); // the page the first render could not see yet, committed now
    return () => {
      observer.disconnect();
      off();
      window.removeEventListener("resize", refresh);
      window.removeEventListener("scroll", refresh, true);
      cancelAnimationFrame(frame.current);
    };
  }, [refresh]);

  const context: Context = {
    info,
    facts: currentFacts(),
    route: pathname,
    phone: document.documentElement.dataset.phone !== undefined,
    passed,
    noneOfThese,
  };
  const welcome = HINTS.find((hint) => hint.id === "welcome")!;

  // The main guide runs while not completed, not closed, the statistics question answered;
  // its welcome shows once per page load while no model is connected (or after Help).
  const running = !info.completed && !closed && holds([["telemetryAnswered"]], context);
  const modelKnown = info.facts?.model ?? null;
  const welcomeDue = !welcomed && (restarted || modelKnown === false);
  const waiting = !welcomed && !restarted && modelKnown === null && !partDone(context, "model");

  if (running && atStart.current === null && !waiting)
    atStart.current = new Set(PARTS.filter(({ part }) => !partDone(context, part)).map(({ part }) => part));
  for (const { part } of PARTS)
    if (running && atStart.current?.has(part) && partDone(context, part)) doneNow.current.add(part);

  let shown: Shown = { mode: "none" };
  let step: Hint | undefined;
  if (running && !waiting) {
    if (welcomeDue) {
      if (holds(welcome.when, context)) shown = { mode: "centred", hint: welcome };
    } else {
      step = HINTS.find(
        (hint) =>
          hint.kind === "guiding" &&
          hint !== welcome &&
          !hint.precede &&
          !skipped.has(hint.id) &&
          !(hint.part && partDone(context, hint.part)) &&
          holds(hint.when, context),
      );
      const before =
        step &&
        context.phone &&
        HINTS.find(
          (hint) =>
            hint.precede &&
            hint.part === step!.part &&
            hint.precede.for.includes(step!.target ?? "") &&
            !skipped.has(hint.id) &&
            holds(hint.when, { ...context, next: step }),
        );
      if (before) step = before;
    }
  }
  if (step) {
    if (step.centred) shown = { mode: "centred", hint: step };
    else {
      const target = findMarker(step.target!);
      const windows = openWindows();
      if (windows.some((one) => !target || !one.contains(target))) shown = { mode: "hidden" };
      else if (!target) shown = { mode: "missing", hint: step };
      else
        shown = {
          mode: "step",
          hint: step,
          target,
          anchor: step.anchor ? findMarker(step.anchor) : null,
          inWindow: windowOf(target),
        };
    }
  }

  // Tips: only while no guiding step shows or waits; the one shown stays until Got it or
  // until its target leaves; else the first not shown yet whose condition holds.
  if (shown.mode === "none" && !(running && waiting) && !info.tips_off) {
    const current = tip && !tipsDone.has(tip) ? HINTS.find((hint) => hint.id === tip) : undefined;
    const candidate =
      current && holds(current.when, context)
        ? current
        : HINTS.find(
            (hint) =>
              hint.kind === "tip" &&
              !info.shown.includes(hint.id) &&
              !tipsDone.has(hint.id) &&
              !skipped.has(hint.id) &&
              holds(hint.when, context),
          );
    if (candidate) {
      const target = findMarker(candidate.target!);
      shown = target
        ? { mode: "tip", hint: candidate, target, inWindow: windowOf(target) }
        : { mode: "missing", hint: candidate };
    }
  }
  const shownId = "hint" in shown ? shown.hint.id : null;

  // The tip shown now; a tip that went (its target left) is done for the page load.
  useEffect(() => {
    const now = shown.mode === "tip" ? shown.hint.id : null;
    if (now === tip) return;
    if (tip) setTipsDone((done) => new Set(done).add(tip));
    setTip(now);
  });

  // A hint is marked shown as soon as it appears.
  useEffect(() => {
    if (!shownId || shown.mode === "missing" || marked.current.has(shownId)) return;
    marked.current.add(shownId);
    if (!info.shown.includes(shownId)) mark({ action: "shown", ids: [shownId] });
  });

  // Opening the New session window completes the main guide, whichever step shows.
  const launching = findMarker("launch-task") !== null;
  const completing = useRef(false);
  useEffect(() => {
    if (!launching || info.completed || completing.current) return;
    completing.current = true;
    onInfo({ ...info, completed: true });
    mark({ action: "complete" });
  });

  // A marker not on screen for MISSING_MS: the hint is skipped for the page load and journaled.
  const missingId = shown.mode === "missing" ? shown.hint.id : null;
  const missingMarker = shown.mode === "missing" ? shown.hint.target! : "";
  useEffect(() => {
    if (!missingId) return;
    const timer = setTimeout(() => {
      if (findMarker(missingMarker)) return refresh();
      setSkipped((now) => new Set(now).add(missingId));
      mark({ action: "missing", ids: [missingId], marker: missingMarker });
    }, MISSING_MS);
    return () => clearTimeout(timer);
  }, [missingId, missingMarker, mark, refresh]);

  // A login window closed without a login passes its row, once Agent CLIs' check after it ended.
  const sheet = document.querySelector<HTMLElement>('[data-guide="login-sheet"]');
  const sheetCli = sheet && visible(sheet) ? (sheet.dataset.guideCli ?? null) : null;
  const lastSheet = useRef<string | null>(null);
  useEffect(() => {
    if (sheetCli) {
      lastSheet.current = sheetCli;
      closedSheet.current = null;
      return;
    }
    if (lastSheet.current) {
      closedSheet.current = lastSheet.current;
      lastSheet.current = null;
    }
    const cli = closedSheet.current;
    const logins = currentFacts().logins;
    if (!cli || openWindows().length > 0 || !logins || logins.checking) return;
    closedSheet.current = null;
    if (!logins.rows.some((row) => row.name === cli && row.loggedIn)) setPassed((now) => new Set(now).add(cli));
  });

  const close = () => setClosed(true);
  const act = (hint: Hint, index: number) => {
    if (hint.id === "welcome") return index === 0 ? setWelcomed(true) : close();
    if (hint.id === "none-of-these") return index === 0 ? setNoneOfThese(false) : close();
  };
  const link = (hint: Hint) => {
    if (hint.action === "pass-row" && hint.cli) setPassed((now) => new Set(now).add(hint.cli!));
    if (hint.action === "none-of-these") setNoneOfThese(true);
  };
  const gotIt = (id: string) => setTipsDone((done) => new Set(done).add(id));
  const tipsOff = () => {
    onInfo({ ...info, tips_off: true });
    mark({ action: "tips_off" });
  };

  // Where the focus was before the guide's first card took it: given back on Not now or Esc,
  // else to the step's target, else to the page's heading.
  const guiding = shown.mode === "centred" || shown.mode === "step";
  if (guiding && focusBefore.current === null) focusBefore.current = document.activeElement;
  if (shown.mode === "step") lastTarget.current = shown.target;
  useEffect(() => {
    if (!closed) return;
    const was = focusBefore.current;
    const back =
      (was instanceof HTMLElement && was.isConnected && was !== document.body ? was : null) ??
      (lastTarget.current?.isConnected ? lastTarget.current : null) ??
      document.querySelector<HTMLElement>("main h2");
    back?.focus({ preventScroll: true });
  }, [closed]);

  if (shown.mode === "none" || shown.mode === "hidden" || shown.mode === "missing") return null;
  const counter = counterOf(shown.hint, atStart.current, doneNow.current);
  const host = shown.mode === "step" || shown.mode === "tip" ? shown.inWindow : null;
  // A layer inside a modal <dialog> (the New session window) is drawn in it, so it sits above
  // the dialog in the top layer and stays usable; elsewhere it is the body's.
  const into = host?.tagName === "DIALOG" ? host : document.body;
  return createPortal(
    <div ref={layer} className="gd-layer">
      {shown.mode === "centred" ? (
        <Centred key={shown.hint.id} hint={shown.hint} onAct={(index) => act(shown.hint, index)} onClose={close} />
      ) : shown.mode === "step" ? (
        <Step
          key={shown.hint.id}
          hint={shown.hint}
          target={shown.target}
          anchor={shown.anchor}
          inWindow={shown.inWindow}
          phone={context.phone}
          counter={counter}
          onLink={() => link(shown.hint)}
          onClose={close}
        />
      ) : (
        <Tip
          key={shown.hint.id}
          hint={shown.hint}
          target={shown.target}
          inWindow={shown.inWindow}
          phone={context.phone}
          onGotIt={() => gotIt(shown.hint.id)}
          onOff={tipsOff}
        />
      )}
    </div>,
    into,
  );
}

// "<part> · Step N of M": the parts left when the guide started, and those done since; the
// done line when the part before was done in this run.
function counterOf(hint: Hint, atStart: Set<Part> | null, doneNow: Set<Part>) {
  if (!hint.part || hint.centred) return { eyebrow: undefined, doneLine: false };
  const counted = PARTS.filter(({ part }) => atStart?.has(part) || doneNow.has(part));
  const at = counted.findIndex(({ part }) => part === hint.part);
  const name = PARTS.find(({ part }) => part === hint.part)!.name;
  const before = PARTS[PARTS.findIndex(({ part }) => part === hint.part) - 1];
  return {
    eyebrow: at < 0 ? name : `${name} · Step ${at + 1} of ${counted.length}`,
    doneLine: before !== undefined && doneNow.has(before.part),
  };
}

// A card takes the focus as it appears only from nobody (the page, a card that went): a step
// the person's action completed leaves the focus where that action put it (a form's field).
const focusIsFree = () =>
  !document.activeElement || document.activeElement === document.body || !document.activeElement.isConnected;

// `inert` on everything but the guide's layer and the path to `keep` (null: everything but
// the layer), removed when the step ends; a <dialog> is never made inert (a window the target
// opens), nor what was inert already.
function useInert(on: boolean, keep: HTMLElement | null) {
  useEffect(() => {
    if (!on) return;
    const set: HTMLElement[] = [];
    const spare = (one: Element) =>
      one.classList.contains("gd-layer") || one.tagName === "DIALOG" || one.tagName === "SCRIPT" || one.hasAttribute("inert");
    const shut = (parent: Element, path: Element | null) => {
      for (const child of parent.children) {
        if (child === path || spare(child) || !(child instanceof HTMLElement)) continue;
        if (child.contains(document.querySelector(".gd-layer"))) continue;
        child.setAttribute("inert", "");
        set.push(child);
      }
    };
    if (keep === null) shut(document.body, null);
    else
      for (let node: HTMLElement | null = keep; node && node !== document.body; node = node.parentElement)
        if (node.parentElement) shut(node.parentElement, node);
    return () => {
      for (const one of set) one.removeAttribute("inert");
    };
  }, [on, keep]);
}

function Body({ texts, id }: { texts: Texts; id: string }) {
  return (
    <div className="gd-body" id={id}>
      {texts.body.map((line) => (
        <p key={line}>
          <Rich text={line} />
        </p>
      ))}
    </div>
  );
}

function Centred({ hint, onAct, onClose }: { hint: Hint; onAct: (index: number) => void; onClose: () => void }) {
  const card = useRef<HTMLDivElement>(null);
  const texts = hint.texts;
  useInert(true, null);
  useEffect(() => {
    card.current?.querySelector<HTMLElement>(".gd-btn")?.focus();
  }, []);
  return (
    <>
      <div className="gd-veil" />
      <div
        ref={card}
        className="gd-card centred"
        role="dialog"
        aria-modal="true"
        aria-labelledby={`gd-${hint.id}-title`}
        aria-describedby={`gd-${hint.id}-body`}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            onClose();
          } else if (event.key === "Tab") keepTab(event, card.current);
        }}
      >
        <h2 className="gd-title big" id={`gd-${hint.id}-title`}>
          {texts.title}
        </h2>
        <Body texts={texts} id={`gd-${hint.id}-body`} />
        {texts.links && (
          <div className="gd-links">
            {texts.links.map((one) => (
              <a key={one.href} className="gd-link" href={one.href} target="_blank" rel="noopener noreferrer">
                {one.label}
              </a>
            ))}
          </div>
        )}
        {texts.help && <p className="gd-help">{texts.help}</p>}
        <div className="gd-foot">
          {(texts.buttons ?? []).map((label, index) => (
            <button key={label} type="button" className={index === 0 ? "gd-btn" : "gd-btn second"} onClick={() => onAct(index)}>
              {label}
            </button>
          ))}
        </div>
        {texts.note && <p className="gd-note">{texts.note}</p>}
      </div>
    </>
  );
}

// Tab and Shift+Tab stay among `within`'s controls (a centred card).
function keepTab(event: React.KeyboardEvent, within: HTMLElement | null) {
  const all = [...(within?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])];
  if (all.length === 0) return;
  const at = all.indexOf(document.activeElement as HTMLElement);
  const next = event.shiftKey ? (at <= 0 ? all.length - 1 : at - 1) : at === all.length - 1 ? 0 : at + 1;
  event.preventDefault();
  all[next].focus();
}

// The card's place, measured after each render and on the engine's refreshes.
function usePlacement(
  card: React.RefObject<HTMLDivElement | null>,
  measure: () => Omit<Parameters<typeof place>[0], "card"> | null,
): Placement | null {
  const [placed, setPlaced] = useState<Placement | null>(null);
  useLayoutEffect(() => {
    const given = measure();
    const box = card.current;
    if (!given || !box) return;
    const found = place({ ...given, card: { w: box.offsetWidth, h: box.offsetHeight } });
    setPlaced((now) => (JSON.stringify(now) === JSON.stringify(found) ? now : found));
  });
  return placed;
}

// Scroll a target not fully in view into it, once per step.
function useInView(target: HTMLElement) {
  useEffect(() => {
    const box = target.getBoundingClientRect();
    if (box.top >= 0 && box.bottom <= window.innerHeight) return;
    const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? true;
    target.scrollIntoView?.({ block: box.height > window.innerHeight / 2 ? "start" : "center", behavior: still ? "auto" : "smooth" });
  }, [target]);
}

const viewport = (): Rect => ({ x: 0, y: 0, w: window.innerWidth, h: window.innerHeight });

function cardStyle(placed: Placement | null, phone: boolean): CSSProperties {
  if (!placed) return { left: 0, top: 0, visibility: "hidden" };
  return { left: placed.x, top: placed.y, ...(phone ? { width: placed.w } : {}) };
}

function Arrow({ placed }: { placed: Placement | null }) {
  if (!placed?.arrow) return null;
  const { side, x, y } = placed.arrow;
  return <span className="gd-arrow" data-side={side} style={{ left: x, top: y }} aria-hidden="true" />;
}

function Step(props: {
  hint: Hint;
  target: HTMLElement;
  anchor: HTMLElement | null;
  inWindow: HTMLElement | null;
  phone: boolean;
  counter: { eyebrow?: string; doneLine: boolean };
  onLink: () => void;
  onClose: () => void;
}) {
  const { hint, target, anchor, inWindow, phone, counter } = props;
  const card = useRef<HTMLDivElement>(null);
  const variant = hint.variants?.[(anchor ?? target).dataset.guideRefusal ?? ""];
  const texts = variant ?? hint.texts;
  useInView(target);
  const placed = usePlacement(card, () => ({
    target: rectOf(target),
    anchor: anchor ? rectOf(anchor) : undefined,
    dialog: inWindow ? rectOf(inWindow.querySelector(".login-window") ?? inWindow) : undefined,
    viewport: viewport(),
    phone,
    kind: "guiding",
    prefer: hint.prefer,
    obstacles: [],
  }));
  // The page is dimmed and inert but for the hole, unless the target's window dims it.
  const dim = !inWindow && (placed?.dim ?? true);
  useInert(dim, target);
  useEffect(() => {
    if (!inWindow && focusIsFree()) card.current?.focus({ preventScroll: true });
  }, [inWindow]);
  const hole = placed?.cutAnchor && anchor ? rectOf(anchor) : rectOf(target);
  const ringed = (inWindow || placed?.ringAnchor) && anchor ? rectOf(anchor) : hole;
  const named = accessibleName(target);
  return (
    <>
      {dim && <Dim hole={hole} />}
      <span className="gd-ring" style={ringBox(ringed, -PAD)} aria-hidden="true" />
      <div
        ref={card}
        className="gd-card"
        role="dialog"
        aria-modal="false"
        tabIndex={-1}
        aria-labelledby={`gd-${hint.id}-title`}
        aria-describedby={`gd-${hint.id}-body`}
        style={cardStyle(placed, phone)}
        onKeyDown={(event) => {
          if (event.key !== "Escape") return;
          event.preventDefault();
          event.stopPropagation();
          props.onClose();
        }}
      >
        <Arrow placed={placed} />
        {counter.doneLine && texts.done && <p className="gd-done">{texts.done}</p>}
        {counter.eyebrow && <p className="gd-eyebrow">{counter.eyebrow}</p>}
        <h2 className="gd-title" id={`gd-${hint.id}-title`}>
          {texts.title}
        </h2>
        <div className="gd-body" id={`gd-${hint.id}-body`}>
          {texts.body.map((line) => (
            <p key={line}>
              <Rich text={line} />
            </p>
          ))}
          {named && <span className="visually-hidden">{`Highlighted: ${named}`}</span>}
        </div>
        {texts.link && (
          <div className="gd-links">
            <button type="button" className="gd-link" onClick={props.onLink}>
              {texts.link}
            </button>
          </div>
        )}
        <div className="gd-foot">
          {texts.waiting && (
            <span className="gd-wait" role="status">
              {texts.waiting}
            </span>
          )}
          <button type="button" className="gd-quiet" onClick={props.onClose}>
            Not now
          </button>
        </div>
      </div>
    </>
  );
}

const ringBox = (r: Rect, inset: number): CSSProperties => ({
  left: r.x + inset,
  top: r.y + inset,
  width: r.w - 2 * inset,
  height: r.h - 2 * inset,
});

// The dim around the hole: four blocks that swallow presses, the hole itself left open.
function Dim({ hole }: { hole: Rect }) {
  const h = { x: hole.x - PAD, y: hole.y - PAD, w: hole.w + 2 * PAD, h: hole.h + 2 * PAD };
  const swallow = (event: React.SyntheticEvent) => {
    event.preventDefault();
    event.stopPropagation();
  };
  const blocks: CSSProperties[] = [
    { left: 0, top: 0, right: 0, height: Math.max(0, h.y) },
    { left: 0, top: h.y + h.h, right: 0, bottom: 0 },
    { left: 0, top: h.y, width: Math.max(0, h.x), height: h.h },
    { left: h.x + h.w, top: h.y, right: 0, height: h.h },
  ];
  return (
    <>
      <span className="gd-hole" style={{ left: h.x, top: h.y, width: h.w, height: h.h }} aria-hidden="true" />
      {blocks.map((style, index) => (
        <span key={index} className="gd-block" style={style} aria-hidden="true" onMouseDown={swallow} onClick={swallow} />
      ))}
    </>
  );
}

function Tip(props: {
  hint: Hint;
  target: HTMLElement;
  inWindow: HTMLElement | null;
  phone: boolean;
  onGotIt: () => void;
  onOff: () => void;
}) {
  const { hint, target, inWindow, phone } = props;
  const card = useRef<HTMLDivElement>(null);
  const gotIt = useRef<HTMLButtonElement>(null);
  const placed = usePlacement(card, () => {
    const focusable = [...document.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
      (one) => !target.contains(one) && !one.closest(".gd-layer") && visible(one) && (!inWindow || inWindow.contains(one)),
    );
    const controls = [...target.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(visible);
    return {
      target: rectOf(target),
      dialog: inWindow && inWindow.tagName === "DIALOG" ? rectOf(inWindow) : undefined,
      viewport: viewport(),
      phone,
      kind: "tip",
      prefer: hint.prefer,
      obstacles: focusable.map(rectOf).filter((r) => r.w > 0 && r.h > 0),
      inTarget: controls.map(rectOf),
    };
  });
  // Tab on the target goes to Got it, Shift+Tab from Got it back; Esc there is Got it.
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      const at = document.activeElement;
      const onTarget = at instanceof Node && target.contains(at);
      const inTip = at instanceof Node && !!card.current?.contains(at);
      if (event.key === "Escape" && (onTarget || inTip)) {
        props.onGotIt();
      } else if (event.key === "Tab" && !event.shiftKey && onTarget) {
        event.preventDefault();
        gotIt.current?.focus();
      } else if (event.key === "Tab" && event.shiftKey && at === gotIt.current) {
        event.preventDefault();
        (target.matches(FOCUSABLE) ? target : target.querySelector<HTMLElement>(FOCUSABLE))?.focus();
      }
    };
    document.addEventListener("keydown", key, true);
    return () => document.removeEventListener("keydown", key, true);
  });
  const text = hint.texts.body.map(plainText).join(" ");
  const pointing = placed && placed.ring === "dashed";
  const body = useMemo(() => `gd-${hint.id}-body`, [hint.id]);
  return (
    <>
      {pointing && <span className="gd-ring pointing" style={ringBox(rectOf(target), -RING_OUT)} aria-hidden="true" />}
      <span className="visually-hidden" aria-live="polite">{`Tip: ${text}`}</span>
      <div ref={card} className="gd-card tip" role="region" aria-label="Tip" style={cardStyle(placed, phone)}>
        <Arrow placed={placed} />
        <Body texts={hint.texts} id={body} />
        <div className="gd-foot">
          <button ref={gotIt} type="button" className="gd-btn small" onClick={props.onGotIt}>
            Got it
          </button>
          <button type="button" className="gd-quiet" onClick={props.onOff}>
            Don't show tips like this
          </button>
        </div>
      </div>
    </>
  );
}
