// The feed in a session's Activity tab (docs/design/ui.md, The human in the session): the
// messages from and to the human and the agents' questions, the flow runs' gates as cards
// and their other events as lines, and behind a switch the agents' messages to each other,
// live from the feed (live.ts); and the composer. What the human sends shows only once the
// feed brings it: nothing ahead of the server.
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link, useLocation } from "react-router";

import { ApiError, HUMAN, writeMessage, type GateInfo, type MessageInfo, type RunEventInfo } from "./api";
import { Body, clock, Preview } from "./ChatText";
import { Gate, GateAnswer, scrollToGate } from "./GateCard";
import { useLive, useLiveStore, type ListLoaded } from "./live";
import { runPath } from "./paths";
import { Meta, Question } from "./Question";

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

type Loaded = { messages: MessageInfo[]; events: RunEventInfo[]; gates: GateInfo[] };

// A gate the human answered (or overrode), whose answer is also the human's bubble.
const answeredByHuman = (gate: GateInfo) => gate.answer !== null && gate.answered_by === HUMAN && gate.answered_at !== null;

// The messages, the run events and the gates shown, in time order (a message or the
// human's answer to a gate before an event of the same moment: the answer moves the run in
// the same transaction); a gate where it opened, the human's answer when it was given.
function entries({ messages, events, gates }: Loaded, agentMessages: boolean): Entry[] {
  const all: Entry[] = [
    ...messages
      .filter((one) => agentMessages || withHuman(one))
      .map((message) => ({ at: Date.parse(message.created_at), message })),
    ...gates.filter(answeredByHuman).map((gate) => ({ at: Date.parse(gate.answered_at ?? ""), answered: gate })),
    ...events.filter((one) => one.kind in RUN_EVENT_LINES).map((event) => ({ at: Date.parse(event.created_at), event })),
    ...gates.map((gate) => ({ at: Date.parse(gate.created_at), gate })),
  ];
  return all.sort((a, b) => a.at - b.at);
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
  messages: ListLoaded<MessageInfo> | null,
  events: ListLoaded<RunEventInfo> | null,
  gates: ListLoaded<GateInfo> | null,
): { error: string } | Loaded | null {
  for (const one of [messages, events, gates]) if (one && "error" in one) return one;
  if (!messages || !events || !gates || "error" in messages || "error" in events || "error" in gates) return null;
  return { messages: messages.items, events: events.items, gates: gates.items };
}

const isGate = (one: Item): one is GateInfo => !Array.isArray(one) && "options" in one;
const isAnswer = (one: Item): one is { answered: GateInfo } => !Array.isArray(one) && "answered" in one;

export function Chat({ session, stopped, agentMessages }: { session: string; stopped: boolean; agentMessages: boolean }) {
  const live = useLiveStore();
  const state = useLive();
  const loaded = all(state.messages[session] ?? null, state.events[session] ?? null, state.gates[session] ?? null);
  const feed = useRef<HTMLDivElement>(null);
  useEffect(() => live.watch("messages", session), [live, session]);
  useEffect(() => live.watch("events", session), [live, session]);
  useEffect(() => live.watch("gates", session), [live, session]);

  const ready = loaded !== null && !("error" in loaded);
  const shown = ready ? entries(loaded, agentMessages) : [];
  const waiting = ready ? loaded.gates.find((gate) => gate.answer === null) : undefined;
  useEffect(() => {
    const element = feed.current;
    if (element) element.scrollTop = element.scrollHeight; // the latest at the bottom
  }, [shown.length]);
  // A link to a card (#gate-<id>, #message-<id>: Needs you, a notification) scrolls to it
  // once the feed is loaded, after the scroll to the latest above.
  const { hash } = useLocation();
  useEffect(() => {
    if (ready && hash) document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView?.({ block: "center" });
  }, [ready, hash]);

  return (
    <section className="chat" aria-label="Chat">
      <div className="chat-feed" role="log" aria-label="Chat with the session" ref={feed}>
        {loaded === null && <p className="muted">Loading…</p>}
        {loaded && "error" in loaded && (
          <p className="problem" role="alert">
            {loaded.error}
          </p>
        )}
        {ready && shown.length === 0 && <p className="empty">No messages yet. Write to the supervisor below.</p>}
        {ready &&
          grouped(shown).map((one) =>
            Array.isArray(one) ? (
              <RunEvents key={`events-${one[0].id}`} session={session} events={one} />
            ) : isGate(one) ? (
              <Gate key={`gate-${one.id}`} session={session} gate={one} stopped={stopped} />
            ) : isAnswer(one) ? (
              <GateAnswer key={`answer-${one.answered.id}`} gate={one.answered} />
            ) : one.kind === "question" ? (
              <Question key={one.id} session={session} question={one} answer={answerOf(one, loaded.messages)} />
            ) : (
              <Message key={one.id} message={one} />
            ),
          )}
      </div>
      {waiting && <GateHint gate={waiting} />}
      <Composer session={session} stopped={stopped} />
    </section>
  );
}

// Over the composer while a gate is open: the composer does not answer it, its card does.
function GateHint({ gate }: { gate: GateInfo }) {
  return (
    <p className="gate-hint">
      Gate #{gate.id} waits:{" "}
      <button type="button" className="link-button" onClick={() => scrollToGate(gate.id)}>
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
    <article className={`chat-message${mine ? " mine" : ""}${between ? " between" : ""}`} aria-label={label}>
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

function Composer({ session, stopped }: { session: string; stopped: boolean }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function send() {
    if (!text.trim() || busy) return;
    setBusy(true);
    setProblem(null);
    try {
      await writeMessage(session, text);
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
        aria-label="Write to the supervisor…"
        placeholder={stopped ? "The session is stopped: resume it to write" : "Write to the supervisor…"}
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
