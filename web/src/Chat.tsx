// The chat in a session's Activity tab (docs/design/ui.md, The human in the session): the
// messages from and to the human and the agents' questions, live from the feed (live.ts),
// and the composer. What the human sends shows only once the feed brings it: nothing ahead
// of the server.
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import Markdown from "react-markdown";

import { answerQuestion, ApiError, dismissQuestion, HUMAN, writeMessage, type MessageInfo } from "./api";
import { useLive, useLiveStore } from "./live";

export function Chat({ session, stopped }: { session: string; stopped: boolean }) {
  const live = useLiveStore();
  const loaded = useLive().messages[session] ?? null;
  const feed = useRef<HTMLDivElement>(null);
  useEffect(() => live.watch("messages", session), [live, session]);

  const count = loaded && "items" in loaded ? loaded.items.length : 0;
  useEffect(() => {
    const element = feed.current;
    if (element) element.scrollTop = element.scrollHeight; // the latest at the bottom
  }, [count]);

  return (
    <section className="chat" aria-label="Chat">
      <div className="chat-feed" role="log" aria-label="Chat with the session" ref={feed}>
        {loaded === null && <p className="muted">Loading…</p>}
        {loaded && "error" in loaded && (
          <p className="problem" role="alert">
            {loaded.error}
          </p>
        )}
        {loaded && "items" in loaded && loaded.items.length === 0 && (
          <p className="empty">No messages yet. Write to the supervisor below.</p>
        )}
        {loaded &&
          "items" in loaded &&
          loaded.items.map((one) =>
            one.kind === "question" ? (
              <Question key={one.id} session={session} question={one} answer={answerOf(one, loaded.items)} />
            ) : (
              <Message key={one.id} message={one} />
            ),
          )}
      </div>
      <Composer session={session} stopped={stopped} />
    </section>
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
      {mine && <span>to {message.to}</span>}
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

function Message({ message }: { message: MessageInfo }) {
  const mine = message.from === HUMAN;
  const summary = <h4 className="chat-summary">{message.summary}</h4>;
  return (
    <article className={`chat-message${mine ? " mine" : ""}`} aria-label={`Message from ${mine ? "you" : message.from}`}>
      <Meta message={message} />
      {message.body ? (
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
