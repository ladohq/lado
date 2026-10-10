// An agent's question to the human (ask_human), in its session's chat and on Needs you: the
// card in its agent's row (FeedRow), without a head of its own. Open, it is answered with a
// choice, own words or both, or dismissed; closed, its choices faded, the chosen one marked,
// and the human's reply under them (docs/design/ui.md, Answer in the question card). The
// card changes only when the feed brings the question closed, whoever answered it. Also what
// the chat says of the human's answer, from the answer's fields.
import { useState, type FormEvent } from "react";

import { answerQuestion, ApiError, dismissQuestion, HUMAN, type MessageInfo } from "./api";
import { Attachments } from "./Attachments";
import { Body, clock } from "./ChatText";
import { MiniAvatar } from "./FeedRow";

// The DOM id of a message's place in the chat: a link to it scrolls there.
export const messageAnchor = (id: number) => `message-${id}`;

// The summaries the core gives the human's answer and dismissal of question #id
// (runtime.answer_question, runtime.dismiss_question): only for an answer whose question is
// not in the window, and to show an own answer of one line without the prefix.
export const answerPrefix = (id: number) => `Answer to #${id}: `;
export const dismissedSummary = (id: number) => `Dismissed #${id}`;

// The human's reply to a question as the chat shows it: a dismissal, or the answer's text
// (the choice, else the own words); and a comment (the text that came with a choice or a
// dismissal).
export type Reply = { dismissed: true; comment: string } | { text: string; comment: string };

// `question` when it is in the window: it says whether this reply dismissed it.
export function replyOf(reply: MessageInfo, question?: MessageInfo): Reply {
  const id = reply.reply_to ?? 0;
  const dismissed = question
    ? question.question_state === "dismissed" && question.answered_by === reply.id
    : !reply.choice && reply.summary === dismissedSummary(id);
  if (dismissed) return { dismissed: true, comment: reply.body };
  if (reply.choice) return { text: reply.choice, comment: reply.body };
  // The body, when there is one, is the whole text (runtime._human_text).
  if (reply.body.trim()) return { text: reply.body, comment: "" };
  const prefix = answerPrefix(id);
  return { text: reply.summary.startsWith(prefix) ? reply.summary.slice(prefix.length) : reply.summary, comment: "" };
}

// `answer`: the human's reply to it, when it is in the window; `anchored`, the reply's
// anchor is on the card (no late line of it stands in the chat; Chat.tsx, feedRows).
export function Question({
  session,
  question,
  answer,
  anchored = false,
}: {
  session: string;
  question: MessageInfo;
  answer?: MessageInfo;
  anchored?: boolean;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const open = question.question_state === "open";
  // What the human wrote goes along with a choice, Send or Dismiss.
  const written = text.trim() !== "";

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
    if (written) void act(() => answerQuestion(session, question.id, { text }));
  }

  return (
    <div className={`chat-question${open ? " open" : ""}`}>
      <p className="question-label">
        Question #{question.id}
        {open && " · waits for you"}
      </p>
      <h4 className="chat-summary">{question.summary}</h4>
      {question.body && <Body text={question.body} />}
      <Attachments session={session} attachments={question.attachments} />
      {open ? (
        <form className="answer" onSubmit={submit}>
          {question.choices && (
            <div className="choices">
              {question.choices.map((choice, i) => (
                <button
                  key={choice}
                  type="button"
                  className={i === 0 ? "primary" : "quiet"}
                  disabled={busy}
                  onClick={() =>
                    // What the human wrote in the field goes along as a comment.
                    void act(() => answerQuestion(session, question.id, written ? { choice, text } : { choice }))
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
              placeholder="Your answer or a comment: it goes with a choice, Send or Dismiss"
              rows={2}
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
          )}
          <div className="answer-actions">
            {question.free_answer && (
              <button type="submit" className={written ? "primary" : "quiet"} disabled={busy || !written}>
                Send
              </button>
            )}
            <button
              type="button"
              className="quiet subdued"
              disabled={busy}
              onClick={() => void act(() => dismissQuestion(session, question.id, written ? text : undefined))}
            >
              {written ? "Dismiss with comment" : "Dismiss"}
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
              {question.choices.map((choice) =>
                choice === answer?.choice ? (
                  <li key={choice} className="chosen">
                    ✓ {choice}
                  </li>
                ) : (
                  <li key={choice}>{choice}</li>
                ),
              )}
            </ul>
          )}
          {question.question_state === "closed" ? (
            <p className="chat-outcome">Closed: the agent left</p>
          ) : (
            <Given question={question} answer={answer} anchored={anchored} />
          )}
        </>
      )}
    </div>
  );
}

// The human's reply in the question's card: who and when, and the answer (the choice and
// the comment, else the own words) as the human typed it; a dismissal, its comment if any.
function Given({ question, answer, anchored }: { question: MessageInfo; answer?: MessageInfo; anchored: boolean }) {
  const dismissed = question.question_state === "dismissed";
  const reply = answer && replyOf(answer, question);
  return (
    <div
      className={`question-answer${dismissed ? " dismissed" : ""}`}
      id={answer && anchored ? messageAnchor(answer.id) : undefined}
    >
      <div className="answer-top">
        <MiniAvatar who={HUMAN} />
        <span className="answer-head">You · {dismissed ? "dismissed" : "answered"}</span>
        {answer && <time dateTime={answer.created_at}>{clock(answer.created_at)}</time>}
      </div>
      {reply && "text" in reply &&
        (answer?.choice ? (
          <>
            <p className="answer-choice">✓ {reply.text}</p>
            {reply.comment && <Body text={reply.comment} breaks />}
          </>
        ) : (
          <Body text={reply.text} breaks />
        ))}
      {reply && "dismissed" in reply && reply.comment && <Body text={reply.comment} breaks />}
    </div>
  );
}
