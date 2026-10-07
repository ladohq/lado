// What the chat says of a question's outcome and of the human's answer to it, from their
// fields (runtime.answer_question, dismiss_question write them).
import { expect, test } from "vitest";

import type { MessageInfo } from "./api";
import { outcome, replyOf } from "./Question";

function message(id: number, more: Partial<MessageInfo> = {}): MessageInfo {
  return {
    id,
    from: "human",
    to: "w1",
    kind: "message",
    summary: "",
    body: "",
    state: "delivered",
    choices: null,
    free_answer: false,
    question_state: null,
    answered_by: null,
    reply_to: null,
    choice: null,
    reply_state: null,
    created_at: "2026-10-03T12:00:00.000Z",
    ...more,
  };
}

const question = (more: Partial<MessageInfo> = {}) =>
  message(5, { from: "w1", to: "human", kind: "question", summary: "Merge?", choices: ["yes", "later"], free_answer: true, ...more });
const answered = (by: number) => question({ question_state: "answered", answered_by: by });
const answer = (more: Partial<MessageInfo>) => message(6, { reply_to: 5, ...more });

test("an answer with a choice says the choice, the human's text under it as a comment", () => {
  const reply = answer({ summary: "Answer to #5: later", body: "after the tag", choice: "later" });
  expect(replyOf(reply, answered(6))).toEqual({ text: "later", comment: "after the tag" });
  expect(replyOf(answer({ summary: "Answer to #5: yes", choice: "yes" }))).toEqual({ text: "yes", comment: "" });
});

test("an own answer of one line is the summary without the core's prefix", () => {
  expect(replyOf(answer({ summary: "Answer to #5: after the release" }), answered(6))).toEqual({
    text: "after the release",
    comment: "",
  });
  // Without the prefix (a summary written otherwise), the summary as it is.
  expect(replyOf(answer({ summary: "after the release" }))).toEqual({ text: "after the release", comment: "" });
});

test("an own answer of more lines is its body, which holds the whole text, the first line once", () => {
  const reply = answer({ summary: "Answer to #5: after the release", body: "after the release\nand the tag" });
  expect(replyOf(reply, answered(6))).toEqual({ text: "after the release\nand the tag", comment: "" });
});

test("a dismissal is told by its question; without the question in the window, by the core's summary", () => {
  const dismissal = answer({ summary: "Dismissed #5" });
  expect(replyOf(dismissal, question({ question_state: "dismissed", answered_by: 6 }))).toEqual({ dismissed: true });
  expect(replyOf(dismissal)).toEqual({ dismissed: true });
  // An own answer of one line has no choice and no body either: it is no dismissal.
  expect(replyOf(answer({ summary: "Answer to #5: no" }))).toEqual({ text: "no", comment: "" });
  // The question says it was answered by this message: no dismissal, whatever its text.
  expect(replyOf(answer({ summary: "Answer to #5: Dismissed #5" }), answered(6))).toEqual({
    text: "Dismissed #5",
    comment: "",
  });
});

test("an answered question says only Answered when the answer is the next entry", () => {
  expect(outcome(answered(6), answer({ choice: "yes" }), true)).toEqual({ text: "✓ Answered" });
});

test("an answered question further from its answer says the choice, or links to the own answer", () => {
  expect(outcome(answered(6), answer({ choice: "yes" }), false)).toEqual({ text: "✓ You chose yes" });
  expect(outcome(answered(6), answer({ summary: "Answer to #5: soon" }), false)).toEqual({
    text: "✓ You answered in your own words",
    link: 6,
  });
  // The answer not in the window: a link to it, which loads up to it.
  expect(outcome(answered(6), undefined, false)).toEqual({ text: "✓ Answered", link: 6 });
});

test("a dismissed or closed question says so", () => {
  expect(outcome(question({ question_state: "dismissed", answered_by: 6 }), undefined, false)).toEqual({ text: "Dismissed" });
  expect(outcome(question({ question_state: "closed" }), undefined, false)).toEqual({ text: "Closed: the agent left" });
});
