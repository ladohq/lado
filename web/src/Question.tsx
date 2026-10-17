// An agent's question to the human (ask_human) once it is closed, in its session's chat: the
// card in its agent's row (FeedRow), without a head of its own: its choices faded, the
// chosen one marked (and only there), the supervisor's recommendation as one quiet line
// (Recommendation.tsx), and the human's reply under them (docs/design/ui.md, Answer in the
// question card). An open question is answered in the waiting card (WaitingCard.tsx) and is
// a line in the feed. Also what the chat says of the human's answer, from the answer's
// fields. A dismissal is "skipped" in the UI's words.
import { HUMAN, type MessageInfo } from "./api";
import { Attachments, ImagePreviews } from "./Attachments";
import { Body, clock } from "./ChatText";
import { MiniAvatar } from "./FeedRow";
import { RecommendationLine } from "./Recommendation";

// The DOM id of a message's place in the chat: a link to it scrolls there.
export const messageAnchor = (id: number) => `message-${id}`;

// The summaries the core gives the human's answer and dismissal of question #id
// (runtime.answer_questions): only for an answer whose question is not in the window, and
// to show an own answer of one line without the prefix.
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
  const text = reply.summary.startsWith(prefix) ? reply.summary.slice(prefix.length) : reply.summary;
  return { text: filesOnly(reply, text) ? "" : text, comment: "" };
}

// Whether an own answer is of files only: the core's summary then names its files
// (runtime._files_line), which the chat shows as files, not as words.
function filesOnly(reply: MessageInfo, text: string): boolean {
  const n = reply.attachments.length;
  return n > 0 && text.startsWith(`${n} file${n === 1 ? "" : "s"}: `);
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
  return (
    <div className="chat-question">
      <p className="question-label">Question #{question.id}</p>
      <h4 className="chat-summary">{question.summary}</h4>
      {question.body && <Body text={question.body} />}
      <Attachments session={session} attachments={question.attachments} />
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
      <RecommendationLine rec={question.recommendation} />
      {question.question_state === "closed" ? (
        <p className="chat-outcome">Closed: the agent left</p>
      ) : (
        <Given session={session} question={question} answer={answer} anchored={anchored} />
      )}
    </div>
  );
}

// The human's reply in the question's card: who and when, then a choice's comment (the
// choice itself is marked only in the card's list) or the own words, as the human typed
// them; a skip, its comment if any; then its files, as the human's message shows them.
function Given({
  session,
  question,
  answer,
  anchored,
}: {
  session: string;
  question: MessageInfo;
  answer?: MessageInfo;
  anchored: boolean;
}) {
  const skipped = question.question_state === "dismissed";
  const reply = answer && replyOf(answer, question);
  const shown = reply && ("dismissed" in reply || answer?.choice ? reply.comment : reply.text);
  return (
    <div
      className={`question-answer${skipped ? " dismissed" : ""}`}
      id={answer && anchored ? messageAnchor(answer.id) : undefined}
    >
      <div className="answer-top">
        <MiniAvatar who={HUMAN} />
        <span className="answer-head">You · {skipped ? "skipped" : "answered"}</span>
        {answer && <time dateTime={answer.created_at}>{clock(answer.created_at)}</time>}
      </div>
      {shown && <Body text={shown} breaks />}
      {answer && <ImagePreviews session={session} attachments={answer.attachments} />}
      {answer && <Attachments session={session} attachments={answer.attachments} />}
    </div>
  );
}
