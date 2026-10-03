// The feed in a session's Activity tab (docs/design/ui.md, The human in the session): the
// messages from and to the human and the agents' questions, the flow runs' events as lines,
// and behind a switch the agents' messages to each other, live from the feed (live.ts); and
// the composer. What the human sends shows only once the feed brings it: nothing ahead of
// the server.
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import Markdown from "react-markdown";
import { Link } from "react-router";

import {
  answerQuestion,
  ApiError,
  dismissQuestion,
  HUMAN,
  writeMessage,
  type MessageInfo,
  type RunEventInfo,
} from "./api";
import { useLive, useLiveStore, type ListLoaded } from "./live";
import { sessionPath } from "./paths";

// The run events the feed shows as lines, and how it names each kind: the one list. (The
// Gates task takes the gates out of it: their cards replace the lines.)
export const RUN_EVENT_LINES: Record<string, string> = {
  flow_start: "started",
  flow: "moved",
  flow_set: "set by the human",
  gate_open: "waits for you",
  gate_answer: "answered",
  flow_end: "ended",
  flow_cancel: "cancelled",
};

const BODY_LINES = 8; // the lines of a body to the human shown before Show all
const BODY_CHARS = 1500; // and at most these characters of them

const withHuman = (message: MessageInfo) => message.from === HUMAN || message.to === HUMAN;

type Entry = { at: number; message: MessageInfo } | { at: number; event: RunEventInfo };

// The messages and the run events shown, in time order (a message before an event of the
// same moment).
function entries(messages: MessageInfo[], events: RunEventInfo[], agentMessages: boolean): Entry[] {
  const all: Entry[] = [
    ...messages
      .filter((one) => agentMessages || withHuman(one))
      .map((message) => ({ at: Date.parse(message.created_at), message })),
    ...events.filter((one) => one.kind in RUN_EVENT_LINES).map((event) => ({ at: Date.parse(event.created_at), event })),
  ];
  return all.sort((a, b) => a.at - b.at);
}

// The messages, and the run events between them, consecutive ones in one list.
function grouped(list: Entry[]): (MessageInfo | RunEventInfo[])[] {
  const out: (MessageInfo | RunEventInfo[])[] = [];
  for (const entry of list) {
    const last = out[out.length - 1];
    if ("message" in entry) out.push(entry.message);
    else if (Array.isArray(last)) last.push(entry.event);
    else out.push([entry.event]);
  }
  return out;
}

function both<A, B>(a: ListLoaded<A> | null, b: ListLoaded<B> | null): { error: string } | [A[], B[]] | null {
  if (a && "error" in a) return a;
  if (b && "error" in b) return b;
  return a === null || b === null ? null : [a.items, b.items];
}

export function Chat({ session, stopped, agentMessages }: { session: string; stopped: boolean; agentMessages: boolean }) {
  const live = useLiveStore();
  const state = useLive();
  const loaded = both(state.messages[session] ?? null, state.events[session] ?? null);
  const feed = useRef<HTMLDivElement>(null);
  useEffect(() => live.watch("messages", session), [live, session]);
  useEffect(() => live.watch("events", session), [live, session]);

  const shown = Array.isArray(loaded) ? entries(loaded[0], loaded[1], agentMessages) : [];
  useEffect(() => {
    const element = feed.current;
    if (element) element.scrollTop = element.scrollHeight; // the latest at the bottom
  }, [shown.length]);

  return (
    <section className="chat" aria-label="Chat">
      <div className="chat-feed" role="log" aria-label="Chat with the session" ref={feed}>
        {loaded === null && <p className="muted">Loading…</p>}
        {loaded && "error" in loaded && (
          <p className="problem" role="alert">
            {loaded.error}
          </p>
        )}
        {Array.isArray(loaded) && shown.length === 0 && (
          <p className="empty">No messages yet. Write to the supervisor below.</p>
        )}
        {Array.isArray(loaded) &&
          grouped(shown).map((one) =>
            Array.isArray(one) ? (
              <RunEvents key={`events-${one[0].id}`} session={session} events={one} />
            ) : one.kind === "question" ? (
              <Question key={one.id} session={session} question={one} answer={answerOf(one, loaded[0])} />
            ) : (
              <Message key={one.id} message={one} />
            ),
          )}
      </div>
      <Composer session={session} stopped={stopped} />
    </section>
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
          <Link to={sessionPath(session, "flows")}>Flows</Link>
        </li>
      ))}
    </ol>
  );
}

function answerOf(question: MessageInfo, messages: MessageInfo[]): MessageInfo | undefined {
  return messages.find((one) => one.id === question.answered_by);
}

function Meta({ message }: { message: MessageInfo }) {
  const mine = message.from === HUMAN;
  return (
    <header className="chat-meta">
      <span className="chat-from">{mine ? "you" : message.from}</span>
      {message.to !== HUMAN && <span>to {message.to}</span>}
      <time dateTime={message.created_at}>{clock(message.created_at)}</time>
    </header>
  );
}

function clock(iso: string): string {
  const when = new Date(iso);
  return Number.isNaN(when.getTime()) ? "" : when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// The body is the agent's text: Markdown, with any HTML in it left out.
function Body({ text }: { text: string }) {
  return (
    <div className="chat-body">
      <Markdown skipHtml>{text}</Markdown>
    </div>
  );
}

// A body to the human, shown at once: its first lines, the rest behind Show all.
function Preview({ text }: { text: string }) {
  const [all, setAll] = useState(false);
  const short = preview(text);
  if (short === text) return <Body text={text} />;
  return (
    <>
      <Body text={all ? text : short} />
      <button type="button" className="link-button" aria-expanded={all} onClick={() => setAll(!all)}>
        {all ? "Show less" : "Show all"}
      </button>
    </>
  );
}

// The text up to its BODY_LINES-th line that is not blank, and at most BODY_CHARS of it.
function preview(text: string): string {
  const lines = text.split("\n");
  let seen = 0;
  let end = lines.length;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim() && ++seen === BODY_LINES) {
      end = i + 1;
      break;
    }
  }
  const head = lines.slice(0, end).join("\n");
  const cut = head.length > BODY_CHARS ? `${head.slice(0, BODY_CHARS)}…` : head;
  return cut.trimEnd() === text.trimEnd() ? text : cut;
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

function Question({ session, question, answer }: { session: string; question: MessageInfo; answer?: MessageInfo }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const open = question.question_state === "open";

  async function act(call: () => Promise<unknown>) {
    setBusy(true);
    setProblem(null);
    try {
      await call();
    } catch (error) {
      setProblem(error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (text.trim()) void act(() => answerQuestion(session, question.id, { text }));
  }

  return (
    <article className={`chat-question${open ? " open" : ""}`} aria-label={`Question from ${question.from}`}>
      <Meta message={question} />
      <h4 className="chat-summary">{question.summary}</h4>
      {question.body && <Body text={question.body} />}
      {open ? (
        <form className="answer" onSubmit={submit}>
          {question.choices && (
            <div className="choices">
              {question.choices.map((choice) => (
                <button
                  key={choice}
                  type="button"
                  className="primary"
                  disabled={busy}
                  onClick={() =>
                    // What the human wrote in the field goes along as a comment.
                    void act(() => answerQuestion(session, question.id, text.trim() ? { choice, text } : { choice }))
                  }
                >
                  {choice}
                </button>
              ))}
            </div>
          )}
          {question.free_answer && (
            <textarea
              aria-label="Your answer"
              placeholder="Your answer"
              rows={2}
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
          )}
          <div className="answer-actions">
            {question.free_answer && (
              <button type="submit" className="quiet" disabled={busy || !text.trim()}>
                Submit
              </button>
            )}
            <button
              type="button"
              className="quiet"
              disabled={busy}
              onClick={() => void act(() => dismissQuestion(session, question.id))}
            >
              Dismiss
            </button>
          </div>
          {problem && (
            <p className="field-problem" role="alert">
              {problem}
            </p>
          )}
        </form>
      ) : (
        <p className="chat-outcome">{outcome(question, answer)}</p>
      )}
    </article>
  );
}

function outcome(question: MessageInfo, answer?: MessageInfo): string {
  switch (question.question_state) {
    case "answered":
      return answer?.choice ? `Answered: ${answer.choice}` : "Answered";
    case "dismissed":
      return "Dismissed";
    default:
      return "Question closed: the agent left";
  }
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
        placeholder={stopped ? "The session is stopped: resume it with lado start" : "Write to the supervisor…"}
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
