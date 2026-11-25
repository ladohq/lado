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
// hint whose marker is not on screen for 2 s is skipped for the page load and journaled. Not
// now and Esc complete the main guide for good, until Help → Getting started.
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useLocation } from "react-router";

import { postGuide, type GuideInfo } from "../api";
import { findMarker, holds, partDone, visible, type Context } from "./conditions";
import { currentFacts, subscribe } from "./facts";
import { AGAIN, HINTS, PARTS, type Hint, type Part, type Texts } from "./hints";
import { GAP, MARGIN, place, PAD, type Placement, type Rect } from "./place";

export const MISSING_MS = 2000; // how long a hint waits for its marker
const RING_OUT = 3; // the pointing ring outside its target
const ANNOUNCE_MS = 150; // a tip's live region, empty, before its text

type Props = {
  info: GuideInfo;
  restarted: boolean; // Help → Getting started in this page load
  onInfo: (change: (now: GuideInfo) => GuideInfo) => void;
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

// What shows of `element`: its box cut to every ancestor that clips it (a list that scrolls
// within the page, like a server's models).
function shownRect(element: Element): Rect {
  let { left, top, right, bottom } = element.getBoundingClientRect();
  for (let box = element.parentElement; box && box !== document.body; box = box.parentElement) {
    const style = getComputedStyle(box);
    if (style.overflowX === "visible" && style.overflowY === "visible") continue;
    const clip = box.getBoundingClientRect();
    left = Math.max(left, clip.left);
    top = Math.max(top, clip.top);
    right = Math.min(right, clip.right);
    bottom = Math.min(bottom, clip.bottom);
  }
  return { x: left, y: top, w: Math.max(0, right - left), h: Math.max(0, bottom - top) };
}

// What a hint's card must not cover (its `keep` markers on screen).
const kept = (hint: Hint): Rect[] =>
  (hint.keep ?? []).flatMap((marker) => {
    const found = findMarker(marker);
    const box = found ? shownRect(found) : null;
    return box && box.w > 0 && box.h > 0 ? [box] : [];
  });

// The box that scrolls `element`: its nearest ancestor that scrolls, else the page.
function scrollerOf(element: HTMLElement): HTMLElement {
  for (let box = element.parentElement; box && box !== document.body; box = box.parentElement)
    if (/(auto|scroll)/.test(getComputedStyle(box).overflowY)) return box;
  return document.documentElement;
}

// A card at the window's edge over its target (a form grown tall on a phone): what scrolls the
// target gets room at its end as tall as the card, kept for the step, and scrolls the target's
// end (its buttons) clear of the card, as far as the field in use, else the target's top, stays
// in sight.
function useRoom(placed: Placement | null, target: HTMLElement) {
  const box = shownRect(target);
  const over = placed?.side === "edge" && placed.y < box.y + box.h && box.y < placed.y + placed.h;
  const most = useRef(0);
  if (over) most.current = Math.max(most.current, Math.ceil(placed.h + MARGIN));
  const room = most.current;
  const edge = over ? placed.y : null;
  const tall = Math.round(target.getBoundingClientRect().height);
  useEffect(() => {
    if (!room) return;
    const scroller = scrollerOf(target);
    const before = scroller.style.paddingBottom;
    scroller.style.paddingBottom = `calc(${getComputedStyle(scroller).paddingBottom} + ${room}px)`;
    return () => {
      scroller.style.paddingBottom = before;
    };
  }, [room, target]);
  useEffect(() => {
    if (edge === null) return;
    const now = target.getBoundingClientRect();
    const field = document.activeElement;
    const sight = field instanceof HTMLElement && target.contains(field) ? field.getBoundingClientRect().top : now.top;
    const scroller = scrollerOf(target);
    const top = scroller === document.documentElement ? 0 : scroller.getBoundingClientRect().top;
    const by = Math.min(now.bottom + GAP - edge, sight - top - MARGIN);
    if (by > 0) scroller.scrollBy({ top: by });
  }, [edge, tall, target]);
}

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

const NAME_MAX = 80;

// The highlighted element's name for a screen reader: its label, else its heading (a window,
// a form), else its words, each element's apart, cut at a word.
export function accessibleName(element: HTMLElement): string {
  const label = element.getAttribute("aria-label");
  if (label) return label;
  const labelled = element.getAttribute("aria-labelledby");
  const named = (labelled ? document.getElementById(labelled) : null) ?? element.querySelector("h1, h2, h3, h4, legend");
  const words: string[] = [];
  const walker = document.createTreeWalker(named ?? element, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) words.push(node.textContent ?? "");
  const text = words.join(" ").replace(/\s+/g, " ").trim();
  if (text.length <= NAME_MAX) return text;
  const cut = text.slice(0, NAME_MAX + 1);
  return `${cut.slice(0, Math.max(cut.lastIndexOf(" "), 1)).trimEnd()}…`;
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
  const [closed, setClosed] = useState(false); // Not now, Esc: completed too
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
      // A mark that fails is shown again next time; answers may come in any order.
      postGuide(action).then((answer) => onInfo((now) => merged(now, answer)), () => {});
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
    onInfo((now) => ({ ...now, completed: true, facts: null }));
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

  // Not now and Esc close the main guide for good, in every browser, until Getting started.
  const close = () => {
    setClosed(true);
    if (info.completed) return;
    onInfo((now) => ({ ...now, completed: true, facts: null }));
    mark({ action: "complete" });
  };
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
    onInfo((now) => ({ ...now, tips_off: true }));
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
    const heading = () => {
      // The page's heading, focusable by script only, else the page's content.
      const found = ["main h1, main h2", ".topbar h1", "main"]
        .map((selector) => document.querySelector<HTMLElement>(selector))
        .find(Boolean);
      if (found && !found.matches(FOCUSABLE)) found.tabIndex = -1;
      return found;
    };
    // The first that takes the focus: a row or a note highlighted takes none.
    const candidates = [
      was instanceof HTMLElement && was.isConnected && was !== document.body ? was : null,
      lastTarget.current?.isConnected ? lastTarget.current : null,
    ];
    for (const one of candidates) {
      one?.focus({ preventScroll: true });
      if (one && document.activeElement === one) return;
    }
    heading()?.focus({ preventScroll: true });
  }, [closed]);

  if (shown.mode === "none" || shown.mode === "hidden" || shown.mode === "missing") return null;
  const counter = counterOf(shown.hint, doneNow.current);
  const host = shown.mode === "step" || shown.mode === "tip" ? shown.inWindow : null;
  // A layer over a window of the app is drawn in it: in a modal <dialog> (the New session
  // window) so it sits above it in the top layer and stays usable, in a dialog of the app's
  // own (the login sheet, aria-modal) so a screen reader, which reads only the modal dialog,
  // reads it too; elsewhere it is the body's.
  const into = host?.tagName === "DIALOG" || host?.getAttribute("aria-modal") === "true" ? host : document.body;
  return createPortal(
    <div ref={layer} className="gd-layer">
      {shown.mode === "centred" ? (
        <Centred
          key={shown.hint.id}
          hint={shown.hint}
          texts={shown.hint === welcome ? welcomeTexts(welcome, context) : shown.hint.texts}
          onAct={(index) => act(shown.hint, index)}
          onClose={close}
        />
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

// A mark's answer taken into the record the page holds: what this page load completed,
// turned off or showed stays so, whatever older answer comes later (only Help's restart,
// mount.tsx, takes a record as it is).
export function merged(now: GuideInfo, answer: GuideInfo): GuideInfo {
  const completed = now.completed || answer.completed;
  return {
    ...answer,
    completed,
    tips_off: now.tips_off || answer.tips_off,
    shown: [...new Set([...now.shown, ...answer.shown])],
    facts: completed ? null : (answer.facts ?? now.facts),
  };
}

// "<part> · Step N of M": the part's place on the whole path, the same on every page load
// whatever is done already; the done line when the part before was done in this run.
function counterOf(hint: Hint, doneNow: Set<Part>) {
  if (!hint.part || hint.centred) return { eyebrow: undefined, doneLine: false };
  const at = PARTS.findIndex(({ part }) => part === hint.part);
  const before = PARTS[at - 1];
  return {
    eyebrow: `${PARTS[at].name} · Step ${at + 1} of ${PARTS.length}`,
    doneLine: before !== undefined && doneNow.has(before.part),
  };
}

// The welcome's texts for what is left of the path (Getting started on a LADO set up).
function welcomeTexts(hint: Hint, context: Context): Texts {
  if (!partDone(context, "model")) return hint.texts;
  return (partDone(context, "author") ? hint.variants?.ready : hint.variants?.author) ?? hint.texts;
}

// A card takes the focus as it appears only from nobody (the page, a card that went, a part
// of the page the step just made inert, like the rail link that was pressed): a step the
// person's action completed leaves the focus where that action put it (a form's field).
const focusIsFree = () => {
  const at = document.activeElement;
  return !at || at === document.body || !at.isConnected || at.closest("[inert]") !== null;
};

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

function Body({ texts, id, children }: { texts: Texts; id: string; children?: ReactNode }) {
  return (
    <div className="gd-body" id={id}>
      {texts.body.map((line) => (
        <p key={line}>
          <Rich text={line} />
        </p>
      ))}
      {children}
    </div>
  );
}

function Centred({
  hint,
  texts,
  onAct,
  onClose,
}: {
  hint: Hint;
  texts: Texts;
  onAct: (index: number) => void;
  onClose: () => void;
}) {
  const card = useRef<HTMLDivElement>(null);
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
    target: shownRect(target),
    anchor: anchor ? shownRect(anchor) : undefined,
    dialog: inWindow ? rectOf(inWindow.querySelector(".login-window") ?? inWindow) : undefined,
    viewport: viewport(),
    phone,
    kind: "guiding",
    prefer: hint.prefer,
    obstacles: kept(hint),
  }));
  // The page is dimmed and inert but for the hole, unless the target's window dims it or the
  // step leads elsewhere on the page.
  const dim = hint.dim !== false && !inWindow && (placed?.dim ?? true);
  useInert(dim, target);
  // Once placed: hidden until then, the card cannot take the focus.
  const focused = useRef(false);
  const shownNow = placed !== null;
  useEffect(() => {
    if (focused.current || !shownNow || inWindow) return;
    focused.current = true;
    if (focusIsFree()) card.current?.focus({ preventScroll: true });
  }, [shownNow, inWindow]);
  const hole = placed?.cutAnchor && anchor ? shownRect(anchor) : shownRect(target);
  const ringed = (inWindow || placed?.ringAnchor) && anchor ? shownRect(anchor) : hole;
  useRoom(placed, target);
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
        <Body texts={texts} id={`gd-${hint.id}-body`}>
          {named && <span className="visually-hidden">{`Highlighted: ${named}`}</span>}
        </Body>
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
        <p className="gd-again">{AGAIN}</p>
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
      target: shownRect(target),
      dialog: inWindow && inWindow.tagName === "DIALOG" ? rectOf(inWindow) : undefined,
      viewport: viewport(),
      phone,
      kind: "tip",
      prefer: hint.prefer,
      obstacles: [...focusable.map(rectOf).filter((r) => r.w > 0 && r.h > 0), ...kept(hint)],
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
  // Announced once: the live region comes empty and gets its text just after, as a region
  // that arrives with its text is read out unreliably.
  const [said, setSaid] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setSaid(`Tip: ${hint.texts.body.map(plainText).join(" ")}`), ANNOUNCE_MS);
    return () => clearTimeout(timer);
  }, [hint]);
  const pointing = placed && placed.ring === "dashed";
  return (
    <>
      {pointing && <span className="gd-ring pointing" style={ringBox(shownRect(target), -RING_OUT)} aria-hidden="true" />}
      <span className="visually-hidden" aria-live="polite">
        {said}
      </span>
      <div ref={card} className="gd-card tip" role="region" aria-label="Tip" style={cardStyle(placed, phone)}>
        <Arrow placed={placed} />
        <Body texts={hint.texts} id={`gd-${hint.id}-body`} />
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
