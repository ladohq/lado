// The feed in a session's Activity tab (docs/design/ui.md, The human in the session): the
// messages from and to the human and the agents' questions, the flow runs' gates as cards
// and their other events as lines, and behind a switch the agents' messages to each other,
// live from the feed (live.ts); and the composer. Each message, question and open gate is a
// row (FeedRow), grouped by sender, with a divider between days. What the human sends shows
// only once the feed brings it: nothing ahead of the server.
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type RefObject } from "react";
import { Link, useLocation } from "react-router";

import { ApiError, HUMAN, writeMessage, type GateInfo, type MessageInfo, type RunEventInfo } from "./api";
import { Body, clock, day, dayName, Preview } from "./ChatText";
import { FeedRow } from "./FeedRow";
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
import { messageAnchor, Question, replyOf, type Reply } from "./Question";

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

export type Entry =
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

// A row of the chat: a day's divider (the time of its first entry), run events in one list,
// a message or question and whether it continues the group above it, a gate, or the
// human's answer to a gate.
export type FeedItem =
  | { day: string }
  | { events: RunEventInfo[] }
  | { message: MessageInfo; continued: boolean }
  | { gate: GateInfo }
  | { answered: GateInfo };

// How long after the row above a message still continues its group.
const GROUP_GAP = 5 * 60 * 1000;

const localDay = (at: number) => new Date(at).toDateString();
const parties = (message: MessageInfo) => `${message.from}\n${message.to}`;

// The entries as rows: a divider between entries of different local days, consecutive run
// events in one list, and a message continues the group above it (its row has no head) when
// the row above is a message of the same sender to the same recipient less than GROUP_GAP
// before, neither of them `quiet` (a line of its own: a dismissal). So a divider, a run
// event, a gate or the human's answer to a gate between ends a group.
export function feedRows(list: Entry[], quiet: (message: MessageInfo) => boolean = () => false): FeedItem[] {
  const out: FeedItem[] = [];
  let previous: Entry | undefined;
  for (const entry of list) {
    if (previous && localDay(previous.at) !== localDay(entry.at)) out.push({ day: new Date(entry.at).toISOString() });
    const last = out[out.length - 1];
    if ("message" in entry) {
      const { message } = entry;
      const continued =
        last !== undefined &&
        "message" in last &&
        previous !== undefined &&
        entry.at - previous.at < GROUP_GAP &&
        parties(last.message) === parties(message) &&
        !quiet(last.message) &&
        !quiet(message);
      out.push({ message, continued });
    } else if ("gate" in entry) out.push({ gate: entry.gate });
    else if ("answered" in entry) out.push({ answered: entry.answered });
    else if (last && "events" in last) last.events.push(entry.event);
    else out.push({ events: [entry.event] });
    previous = entry;
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
        {ready && <Rows session={session} entries={shown} messages={loaded.window.items} stopped={stopped} go={go} />}
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

// The chat's rows (feedRows) as they show: the human's reply to a question as their answer
// or a quiet line, read with the question when it is in the window.
function Rows({
  session,
  entries,
  messages,
  stopped,
  go,
}: {
  session: string;
  entries: Entry[];
  messages: MessageInfo[];
  stopped: boolean;
  go: (anchor: string) => void;
}) {
  const byId = new Map(messages.map((one) => [one.id, one]));
  const replies = new Map<number, Reply>();
  for (const one of messages) {
    if (one.from === HUMAN && one.reply_to !== null) replies.set(one.id, replyOf(one, byId.get(one.reply_to)));
  }
  const quiet = (one: MessageInfo) => {
    const reply = replies.get(one.id);
    return reply !== undefined && "dismissed" in reply;
  };
  const rows = feedRows(entries, quiet);
  return rows.map((row, i) => {
    if ("day" in row) return <DayDivider key={`day-${row.day}`} at={row.day} />;
    if ("events" in row) return <RunEvents key={`events-${row.events[0].id}`} session={session} events={row.events} />;
    if ("gate" in row) return <Gate key={`gate-${row.gate.id}`} session={session} gate={row.gate} stopped={stopped} />;
    if ("answered" in row) return <GateAnswer key={`answer-${row.answered.id}`} gate={row.answered} go={go} />;
    const { message, continued } = row;
    const reply = replies.get(message.id);
    if (reply !== undefined) return <Answer key={message.id} message={message} reply={reply} continued={continued} go={go} />;
    if (message.kind !== "question") return <Message key={message.id} message={message} continued={continued} />;
    const answer = message.answered_by === null ? undefined : byId.get(message.answered_by);
    const below = rows[i + 1];
    const next = answer !== undefined && below !== undefined && "message" in below && below.message.id === answer.id;
    return (
      <FeedRow
        key={message.id}
        kind="agent"
        who={message.from}
        at={message.created_at}
        continued={continued}
        label={`Question from ${message.from}`}
        id={messageAnchor(message.id)}
      >
        <Question session={session} question={message} answer={answer} next={next} go={go} />
      </FeedRow>
    );
  });
}

// Between entries of two local days: the later day's name.
function DayDivider({ at }: { at: string }) {
  const name = dayName(at);
  return (
    <div className="chat-day" role="separator" aria-label={name}>
      <span>{name}</span>
    </div>
  );
}

// The human's reply to a question: a dismissal, one quiet line; an answer, the human's row
// with the answer (the choice, else the own words) and the comment under a choice.
function Answer({
  message,
  reply,
  continued,
  go,
}: {
  message: MessageInfo;
  reply: Reply;
  continued: boolean;
  go: (anchor: string) => void;
}) {
  const asked = message.reply_to ?? 0;
  if ("dismissed" in reply) {
    return (
      <article className="chat-quiet" id={messageAnchor(message.id)} aria-label={`You dismissed question #${asked}`}>
        <span>You dismissed question #{asked}</span> <time dateTime={message.created_at}>{clock(message.created_at)}</time>
      </article>
    );
  }
  const aside = (
    <>
      → {message.to} · answer to{" "}
      <a
        href={`#${messageAnchor(asked)}`}
        onClick={(event) => {
          event.preventDefault();
          go(messageAnchor(asked));
        }}
      >
        #{asked}
      </a>
    </>
  );
  return (
    <FeedRow
      kind="human"
      who="You"
      aside={aside}
      at={message.created_at}
      continued={continued}
      label="Message from you"
      id={messageAnchor(message.id)}
      className="chat-message"
    >
      <h4 className="chat-summary chat-answer">{reply.text}</h4>
      {reply.comment && <p className="chat-comment">{reply.comment}</p>}
      {message.state === "failed" && <p className="chat-note">not delivered</p>}
    </FeedRow>
  );
}

function Message({ message, continued }: { message: MessageInfo; continued: boolean }) {
  const mine = message.from === HUMAN;
  const between = !withHuman(message);
  const summary = <h4 className={`chat-summary${message.body ? " lead" : ""}`}>{message.summary}</h4>;
  const label = between ? `Message from ${message.from} to ${message.to}` : `Message from ${mine ? "you" : message.from}`;
  return (
    <FeedRow
      kind={mine ? "human" : "agent"}
      who={mine ? "You" : message.from}
      aside={message.to === HUMAN ? undefined : `→ ${message.to}`}
      at={message.created_at}
      continued={continued}
      label={label}
      id={messageAnchor(message.id)}
      className={`chat-message${between ? " between" : ""}`}
    >
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
    </FeedRow>
  );
}

// The lines the composer's field grows to before it scrolls.
const COMPOSER_LINES = 8;

// The field as tall as its text, from 1 line to COMPOSER_LINES, then it scrolls.
function grow(field: HTMLTextAreaElement | null) {
  if (!field) return;
  const style = getComputedStyle(field);
  const line = parseFloat(style.lineHeight) || 20;
  const padding = (parseFloat(style.paddingTop) || 0) + (parseFloat(style.paddingBottom) || 0);
  const most = line * COMPOSER_LINES + padding;
  field.style.height = "auto";
  const height = field.scrollHeight;
  field.style.height = `${Math.min(height, most)}px`;
  field.style.overflowY = height > most ? "auto" : "hidden";
}

// The human's text to the supervisor, or to agent `to` (an agent's page): one frame with
// the field, which grows with the text, and Send; under it to whom and how to send.
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
  const own = useRef<HTMLTextAreaElement>(null);
  const field = inputRef ?? own;
  useLayoutEffect(() => grow(field.current), [text, field]);

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
      <div className="composer-box">
        <textarea
          ref={field}
          aria-label={`Write to ${to ?? "the supervisor"}…`}
          placeholder={stopped ? "The session is stopped: resume it to write" : `Write to ${to ?? "the supervisor"}…`}
          rows={1}
          value={text}
          disabled={stopped}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={keyDown}
        />
        <button type="submit" className="send" disabled={stopped || busy || !text.trim()}>
          Send
        </button>
      </div>
      <p className="composer-meta">
        <span className="composer-to">
          to <span className="composer-name">{to ?? "supervisor"}</span>
        </span>
        <span className="composer-keys">Enter to send · Shift+Enter for a new line</span>
      </p>
      {problem && (
        <p className="field-problem" role="alert">
          {problem}
        </p>
      )}
    </form>
  );
}
