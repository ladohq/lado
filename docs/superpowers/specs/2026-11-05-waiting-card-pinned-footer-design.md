# The waiting card with a pinned footer

Task LAD-194, from the audit LAD-189 (F14, F18, F19). Source of the look: LAD-189 spec §3 and §9,
frames g3-*; where they differ, the human's decisions in the change's proposal win. Requirements:
`openspec/changes/waiting-card-pinned-footer/`. Decisions: its `design.md`, D1 to D15.

## What the human sees

A gate's tab reads from top to bottom: its question, the note that scrolls, the recommendation in
one line, the comment field of one line, the buttons. Whatever the note's length, the last three
are in sight. A cut note fades and offers "↓ more", which is Expand.

A question's tab is the same with chips for the comment field. Other… opens the field under the
chips, the composer below folds into "Answering question #5 above · Write to supervisor instead",
so only one field talks to the agent. Skip question stands beside Send and does what Skip did. A
tab of several questions keeps today's list inside the context, with Send and the count below.

On a phone the footer fits the keyboard by itself, so a field's focus expands nothing: the context
and the Team row step aside, and the composer folds, until the focus leaves.

## Layout

```
.waiting-card                     flex column, height by content
  .waiting-head                   tabs, Minimize, Expand; unchanged
  .waiting-panel                  flex column, no padding
    .waiting-top                  max 40 % of the chat, shrinks first
      .waiting-title              2 lines + meta; absent for several questions
      .waiting-context            the one scroller; fade; "↓ more"
    .waiting-foot                 flex none as a whole; line above
      RecommendationBar           one line; opens to 3
      .waiting-choices            by content to 4 rows, then scrolls
      AnswerBox                   1 to 4 lines
      .waiting-send               never shrinks
```

Heights give way from the bottom of the list of importance up: feed and context, title, choices'
area, opened recommendation, field. The buttons never do.

## State

The card keeps what it kept (picks, comments, files, per item) and gains `drafts`, the words of a
field closed by the link, and `typing`, a phone's field in focus. `Chat` gains the fold the card
reports. Nothing goes to the server or to `prefs.ts`: `lado.waitingHeight` was already one value
for all cards, which is what F18 asks.

## Docs

`docs/design/ui.md`, The waiting card: tabs unchanged; **An agent's tab**, **Fields**, the Send row,
**A gate's tab** and **Height** rewritten to this layout, with the decision's date and task; Flow
gates: the recommendation's two forms; Phone layout: LAD-126's expansion replaced by the fold.
CHANGELOG.md: one item under Improved in `## 0.45.0 (unreleased)`. The minor is already open.

## Not verified

A real iOS Safari keyboard. The tests imitate it with the app 440 px high, as `usePhoneViewport`
sees it; the build report says so and the human checks it on a device before the merge.
