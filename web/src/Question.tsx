// An agent's question to the human (ask_human), in its session's chat and on Needs you:
// open, a card answered with a choice, own words or both, or dismissed; closed, its outcome.
// The card changes only when the feed brings the question closed, whoever answered it.
import { useState, type FormEvent } from "react";

import { answerQuestion, ApiError, dismissQuestion, HUMAN, type MessageInfo } from "./api";
import { Body, clock } from "./ChatText";

// The DOM id of a message's place in the chat: a link to it scrolls there.
export const messageAnchor = (id: number) => `message-${id}`;

export function Meta({ message }: { message: MessageInfo }) {
  const mine = message.from === HUMAN;
  return (
    <header className="chat-meta">
      <span className="chat-from">{mine ? "you" : message.from}</span>
      {message.to !== HUMAN && <span>to {message.to}</span>}
      <time dateTime={message.created_at}>{clock(message.created_at)}</time>
    </header>
  );
}

export function Question({ session, question, answer }: { session: string; question: MessageInfo; answer?: MessageInfo }) {
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
    <article
      className={`chat-question${open ? " open" : ""}`}
      id={messageAnchor(question.id)}
      aria-label={`Question from ${question.from}`}
    >
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
