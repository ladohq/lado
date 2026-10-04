// The feed in a session's Activity tab (docs/design/ui.md, The human in the session): the
// messages from and to the human and the agents' questions, the flow runs' gates as cards
// and their other events as lines, and behind a switch the agents' messages to each other,
// live from the feed (live.ts); and the composer. What the human sends shows only once the
// feed brings it: nothing ahead of the server.
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type RefObject } from "react";
import { Link, useLocation } from "react-router";

import { ApiError, HUMAN, writeMessage, type GateInfo, type MessageInfo, type RunEventInfo } from "./api";
import { Body, clock, day, Preview } from "./ChatText";
import { Gate, GateAnswer, gateAnchor } from "./GateCard";
import {
  messageWindow,
  useLive,
  useLiveStore,
  windowKey,
  type ListLoaded,
  type MessageSpec,
  type MessageWindow,
  type WindowLoaded,
} from "./live";
import { runPath } from "./paths";
import { messageAnchor, Meta, Question } from "./Question";

// The run events the feed shows as lines, and how it names each kind: the one list. A
// gate's events are not in it: the gate's card or line stands for them.
export const RUN_EVENT_LINES: Record<string, string> = {
  flow_start: "started",
  flow: "moved",
  flow_set: "set by the human",
  flow_end: "ended",
  flow_cancel: "cancelled",
};

const withHuman = (message: MessageInfo) => message.from === HUMAN || message.to === HUMAN;

type Entry =
  | { at: number; message: MessageInfo }
  | { at: number; event: RunEventInfo }
  | { at: number; gate: GateInfo }
  | { at: number; answered: GateInfo };

// The window of messages the chat opens with and pages back through.
const PAGE = 50;

type Loaded = { window: MessageWindow; events: RunEventInfo[]; gates: GateInfo[] };

// A gate the human answered (or overrode), whose answer is also the human's bubble.
const answeredByHuman = (gate: GateInfo) => gate.answer !== null && gate.answered_by === HUMAN && gate.answered_at !== null;

// The messages, the run events and the gates shown, in time order (a message or the
// human's answer to a gate before an event of the same moment: the answer moves the run in
// the same transaction); a gate where it opened, the human's answer when it was given.
// Gates and events come whole: those before the window's messages wait until they load.
function entries({ window, events, gates }: Loaded): Entry[] {
  const from = window.from === null ? -Infinity : Date.parse(window.from);
  const all: Entry[] = [
    ...window.items.map((message) => ({ at: Date.parse(message.created_at), message })),
    ...gates.filter(answeredByHuman).map((gate) => ({ at: Date.parse(gate.answered_at ?? ""), answered: gate })),
    ...events.filter((one) => one.kind in RUN_EVENT_LINES).map((event) => ({ at: Date.parse(event.created_at), event })),
    ...gates.map((gate) => ({ at: Date.parse(gate.created_at), gate })),
  ];
  return all.filter((one) => one.at >= from).sort((a, b) => a.at - b.at);
}

// An entry's own key: what the scroll rule compares.
function entryKey(entry: Entry | undefined): string | null {
  if (entry === undefined) return null;
  if ("message" in entry) return `message-${entry.message.id}`;
  if ("gate" in entry) return `gate-${entry.gate.id}`;
  if ("answered" in entry) return `answer-${entry.answered.id}`;
  return `event-${entry.event.id}`;
}

type Item = MessageInfo | GateInfo | { answered: GateInfo } | RunEventInfo[];

// The messages, gates and answers, and the run events between them, consecutive ones in
// one list.
function grouped(list: Entry[]): Item[] {
  const out: Item[] = [];
  for (const entry of list) {
    const last = out[out.length - 1];
    if ("message" in entry) out.push(entry.message);
    else if ("gate" in entry) out.push(entry.gate);
    else if ("answered" in entry) out.push({ answered: entry.answered });
    else if (Array.isArray(last)) last.push(entry.event);
    else out.push([entry.event]);
  }
  return out;
}

// The three lists once all are loaded; the first one that failed; or null while loading.
function all(
  window: WindowLoaded | undefined,
  events: ListLoaded<RunEventInfo> | null,
  gates: ListLoaded<GateInfo> | null,
): { error: string } | Loaded | null {
  for (const one of [window, events, gates]) if (one && "error" in one) return one;
  if (!window || !events || !gates || "error" in window || "error" in events || "error" in gates) return null;
  return { window, events: events.items, gates: gates.items };
}

const isGate = (one: Item): one is GateInfo => !Array.isArray(one) && "options" in one;
const isAnswer = (one: Item): one is { answered: GateInfo } => !Array.isArray(one) && "answered" in one;

// Where the feed's scroll stood after the last render, for the scroll rule.
type Scroll = { window: string | null; first: string | null; last: string | null; height: number; top: number; bottom: boolean };

const atBottom = (element: HTMLElement) => element.scrollHeight - element.scrollTop - element.clientHeight < 40;

export function Chat({ session, stopped, agentMessages }: { session: string; stopped: boolean; agentMessages: boolean }) {
  const live = useLiveStore();
  const state = useLive();
  const spec: MessageSpec = agentMessages ? { limit: PAGE } : { with: HUMAN, limit: PAGE };
  const key = windowKey(spec);
  const window = messageWindow(state, session, spec);
  const loaded = all(window, state.events[session] ?? null, state.gates[session] ?? null);
  const feed = useRef<HTMLDivElement>(null);
  const top = useRef<HTMLDivElement>(null);
  const scroll = useRef<Scroll>({ window: null, first: null, last: null, height: 0, top: 0, bottom: true });
  useEffect(() => live.watchMessages(session, spec), [live, session, key]); // key: the spec's
  useEffect(() => live.watch("events", session), [live, session]);
  useEffect(() => live.watch("gates", session), [live, session]);

  const ready = loaded !== null && !("error" in loaded);
  const shown = ready ? entries(loaded) : [];
  const waiting = ready ? loaded.gates.find((gate) => gate.answer === null) : undefined;
  const earlier = ready && loaded.window.earlier && !loaded.window.loadingEarlier && loaded.window.problem === null;
  const loadEarlier = () => live.loadEarlier(session, spec);

  // The scroll rule: to the bottom when the chat opens or changes its window, and when an
  // entry comes at the bottom while the human is there; entries put in front keep what the
  // human sees where it was.
  const first = entryKey(shown[0]);
  const last = entryKey(shown[shown.length - 1]);
  useLayoutEffect(() => {
    const element = feed.current;
    if (!element || !ready) return;
    const was = scroll.current;
    if (was.window !== key) element.scrollTop = element.scrollHeight;
    else if (first !== was.first && was.height > 0) element.scrollTop = was.top + element.scrollHeight - was.height;
    else if (last !== was.last && was.bottom) element.scrollTop = element.scrollHeight;
    scroll.current = { window: key, first, last, height: element.scrollHeight, top: element.scrollTop, bottom: atBottom(element) };
  });
  const scrolled = () => {
    const element = feed.current;
    if (!element) return;
    Object.assign(scroll.current, { height: element.scrollHeight, top: element.scrollTop, bottom: atBottom(element) });
  };

  // The marker at the top: in view (or near it), the page before the window loads. It is
  // observed again after each load, so a page that does not fill the feed loads the next.
  useEffect(() => {
    const marker = top.current;
    if (!marker || !earlier || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((seen) => seen.some((one) => one.isIntersecting) && loadEarlier(), {
      root: feed.current,
      rootMargin: "200px 0px 0px 0px",
    });
    observer.observe(marker);
    return () => observer.disconnect();
  }, [earlier, first, live, session, key]); // loadEarlier is the window's

  // A link to a card (#gate-<id>, #message-<id>: Needs you, a gate's answer, the hint over
  // the composer) scrolls to it; one before the window first loads up to it, in one load.
  const { hash } = useLocation();
  const [goal, setGoal] = useState<string | null>(null);
  const go = (anchor: string) => {
    if (!ready) return;
    const card = document.getElementById(anchor);
    if (card) {
      card.scrollIntoView?.({ block: "center" });
      return;
    }
    const [, kind, id] = /^(message|gate)-(\d+)$/.exec(anchor) ?? [];
    const gate = kind === "gate" ? loaded.gates.find((one) => one.id === Number(id)) : undefined;
    const target = kind === "message" ? { id: Number(id) } : gate ? { at: gate.created_at } : null;
    if (target === null) return;
    setGoal(anchor);
    void live.loadUpTo(session, spec, target).then(() => setGoal((now) => (now === anchor ? null : now)));
  };
  useLayoutEffect(() => {
    if (goal === null) return;
    const card = document.getElementById(goal);
    if (!card) return;
    card.scrollIntoView?.({ block: "center" });
    setGoal(null);
  });
  useEffect(() => {
    if (hash) go(decodeURIComponent(hash.slice(1))); // once per address, when loaded
  }, [ready, hash]);

  return (
    <section className="chat" aria-label="Chat">
      <div className="chat-feed" role="log" aria-label="Chat with the session" ref={feed} onScroll={scrolled}>
        {loaded === null && <p className="muted">Loading…</p>}
        {loaded && "error" in loaded && (
          <p className="problem" role="alert">
            {loaded.error}
          </p>
        )}
        {ready && <Top session={session} window={loaded.window} first={shown[0]} retry={loadEarlier} marker={top} />}
        {ready && shown.length === 0 && <p className="empty">No messages yet. Write to the supervisor below.</p>}
        {ready &&
          grouped(shown).map((one) =>
            Array.isArray(one) ? (
              <RunEvents key={`events-${one[0].id}`} session={session} events={one} />
            ) : isGate(one) ? (
              <Gate key={`gate-${one.id}`} session={session} gate={one} stopped={stopped} />
            ) : isAnswer(one) ? (
              <GateAnswer key={`answer-${one.answered.id}`} gate={one.answered} go={go} />
            ) : one.kind === "question" ? (
              <Question key={one.id} session={session} question={one} answer={answerOf(one, loaded.window.items)} />
            ) : (
              <Message key={one.id} message={one} />
            ),
          )}
      </div>
      {waiting && <GateHint gate={waiting} go={go} />}
      <Composer session={session} stopped={stopped} />
    </section>
  );
}

// The top of the feed: the marker that loads earlier messages, what that load is doing, or
// the start of the session once all is loaded.
function Top({
  session,
  window,
  first,
  retry,
  marker,
}: {
  session: string;
  window: MessageWindow;
  first: Entry | undefined;
  retry: () => void;
  marker: RefObject<HTMLDivElement | null>;
}) {
  if (!window.earlier) {
    return first === undefined ? null : (
      <p className="chat-start">
        Start of session {session} · {day(new Date(first.at).toISOString())}
      </p>
    );
  }
  return (
    <div className="chat-top" ref={marker}>
      {window.loadingEarlier && (
        <p className="chat-loading" role="status">
          Loading earlier messages…
        </p>
      )}
      {window.problem !== null && (
        <p className="problem chat-loading" role="alert">
          Earlier messages could not load: {window.problem}{" "}
          <button type="button" className="link-button" onClick={retry}>
            Retry
          </button>
        </p>
      )}
    </div>
  );
}

// Over the composer while a gate is open: the composer does not answer it, its card does.
function GateHint({ gate, go }: { gate: GateInfo; go: (anchor: string) => void }) {
  return (
    <p className="gate-hint">
      Gate #{gate.id} waits:{" "}
      <button type="button" className="link-button" onClick={() => go(gateAnchor(gate.id))}>
        answer on its card
      </button>
    </p>
  );
}

function RunEvents({ session, events }: { session: string; events: RunEventInfo[] }) {
  return (
    <ol className="run-events" aria-label="Flow runs">
      {events.map((event) => (
        <li key={event.id} className={`run-event run-${event.kind}`}>
          <span className="run-kind">{RUN_EVENT_LINES[event.kind]}</span>{" "}
          <span className="run-text">
            {event.run}: {event.detail}
          </span>{" "}
          <time dateTime={event.created_at}>{clock(event.created_at)}</time>{" "}
          <Link to={runPath(session, event.run)}>Flows</Link>
        </li>
      ))}
    </ol>
  );
}

function answerOf(question: MessageInfo, messages: MessageInfo[]): MessageInfo | undefined {
  return messages.find((one) => one.id === question.answered_by);
}

function Message({ message }: { message: MessageInfo }) {
  const mine = message.from === HUMAN;
  const between = !withHuman(message);
  const summary = <h4 className="chat-summary">{message.summary}</h4>;
  const label = between ? `Message from ${message.from} to ${message.to}` : `Message from ${mine ? "you" : message.from}`;
  return (
    <article
      className={`chat-message${mine ? " mine" : ""}${between ? " between" : ""}`}
      id={messageAnchor(message.id)}
      aria-label={label}
    >
      <Meta message={message} />
      {message.body && message.to === HUMAN ? (
        <>
          {summary}
          <Preview text={message.body} />
        </>
      ) : message.body ? (
        <details>
          <summary>{summary}</summary>
          <Body text={message.body} />
        </details>
      ) : (
        summary
      )}
      {message.state === "failed" && <p className="chat-note">not delivered</p>}
      {message.reply_state === "missing" && <p className="chat-note">{message.to} replied only in its terminal</p>}
    </article>
  );
}

// The human's text to the supervisor, or to agent `to` (an agent's page).
export function Composer({
  session,
  stopped,
  to,
  inputRef,
}: {
  session: string;
  stopped: boolean;
  to?: string;
  inputRef?: RefObject<HTMLTextAreaElement | null>;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function send() {
    if (!text.trim() || busy) return;
    setBusy(true);
    setProblem(null);
    try {
      await writeMessage(session, text, to);
      setText("");
    } catch (error) {
      setProblem(error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send();
    }
  }

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault();
        void send();
      }}
    >
      <textarea
        ref={inputRef}
        aria-label={`Write to ${to ?? "the supervisor"}…`}
        placeholder={stopped ? "The session is stopped: resume it to write" : `Write to ${to ?? "the supervisor"}…`}
        rows={2}
        value={text}
        disabled={stopped}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={keyDown}
      />
      <button type="submit" className="primary" disabled={stopped || busy || !text.trim()}>
        Send
      </button>
      {problem && (
        <p className="field-problem" role="alert">
          {problem}
        </p>
      )}
    </form>
  );
}
