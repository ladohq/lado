// An agent's question to the human (ask_human), in its session's chat and on Needs you: the
// card in its agent's row (FeedRow), without a head of its own. Open, it is answered with a
// choice, own words or both, or dismissed; closed, its choices faded, the chosen one marked,
// and its outcome. The card changes only when the feed brings the question closed, whoever
// answered it. Also what the chat says of the human's answer, from the answer's fields.
import { useState, type FormEvent } from "react";

import { answerQuestion, ApiError, dismissQuestion, type MessageInfo } from "./api";
import { Body } from "./ChatText";

// The DOM id of a message's place in the chat: a link to it scrolls there.
export const messageAnchor = (id: number) => `message-${id}`;

// The summaries the core gives the human's answer and dismissal of question #id
// (runtime.answer_question, runtime.dismiss_question): only for an answer whose question is
// not in the window, and to show an own answer of one line without the prefix.
export const answerPrefix = (id: number) => `Answer to #${id}: `;
export const dismissedSummary = (id: number) => `Dismissed #${id}`;

// The human's reply to a question as the chat shows it: a dismissal, or the answer's text
// (the choice, else the own words) and a comment (the text that came with a choice).
export type Reply = { dismissed: true } | { text: string; comment: string };

// `question` when it is in the window: it says whether this reply dismissed it.
export function replyOf(reply: MessageInfo, question?: MessageInfo): Reply {
  const id = reply.reply_to ?? 0;
  const dismissed = question
    ? question.question_state === "dismissed" && question.answered_by === reply.id
    : !reply.choice && !reply.body && reply.summary === dismissedSummary(id);
  if (dismissed) return { dismissed: true };
  if (reply.choice) return { text: reply.choice, comment: reply.body };
  // The body, when there is one, is the whole text (runtime._human_text).
  if (reply.body.trim()) return { text: reply.body, comment: "" };
  const prefix = answerPrefix(id);
  return { text: reply.summary.startsWith(prefix) ? reply.summary.slice(prefix.length) : reply.summary, comment: "" };
}

// What became of a closed question; `link`, the human's answer to go to. `next`: the answer
// is the entry right under the question, which says the rest.
export function outcome(question: MessageInfo, answer: MessageInfo | undefined, next: boolean): { text: string; link?: number } {
  switch (question.question_state) {
    case "answered":
      if (next) return { text: "✓ Answered" };
      if (answer?.choice) return { text: `✓ You chose ${answer.choice}` };
      if (answer) return { text: "✓ You answered in your own words", link: answer.id };
      return question.answered_by === null ? { text: "✓ Answered" } : { text: "✓ Answered", link: question.answered_by };
    case "dismissed":
      return { text: "Dismissed" };
    default:
      return { text: "Closed: the agent left" };
  }
}

export function Question({
  session,
  question,
  answer,
  next = false,
  go,
}: {
  session: string;
  question: MessageInfo;
  answer?: MessageInfo;
  next?: boolean;
  go?: (anchor: string) => void;
}) {
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
    <div className={`chat-question${open ? " open" : ""}`}>
      <p className="question-label">
        Question #{question.id}
        {open && " · waits for you"}
      </p>
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
        <>
          {question.choices && (
            <ul className="choices closed" aria-label="Choices">
              {question.choices.map((choice) => (
                <li key={choice} className={choice === answer?.choice ? "chosen" : undefined}>
                  {choice}
                </li>
              ))}
            </ul>
          )}
          <Outcome {...outcome(question, answer, next)} go={go} />
        </>
      )}
    </div>
  );
}

function Outcome({ text, link, go }: { text: string; link?: number; go?: (anchor: string) => void }) {
  return (
    <p className="chat-outcome">
      {text}
      {link !== undefined && (
        <>
          {" · "}
          <a
            href={`#${messageAnchor(link)}`}
            onClick={(event) => {
              if (!go) return;
              event.preventDefault();
              go(messageAnchor(link));
            }}
          >
            go to answer
          </a>
        </>
      )}
    </p>
  );
}
