Task: LAD-126

## Why

Symptom: in the web UI on an iPhone, a gate waits in a session's chat; the human taps the
gate's comment field and the keyboard opens. The waiting card shrinks to a strip: its
tabs, a sliver of the field and Approve / Reject; no text can be typed or read (the
task's screenshot). The same happens to a question's own answer (Other…) and a skip's
comment.

Cause (reproduced in Chromium with a touch screen, 402×874, the visible part of the
window 400 px, as the keyboard leaves it): since LAD-109 the phone's app is as high as
the visible part of the window, so with the keyboard open the session's chat keeps
about 250 px. They are shared by the feed, which keeps its least 160 px (`.chat-feed`),
the card, which is at most half the chat, and the composer; the session's tabs and the
Team row take their room above the chat. The card is left with nothing: its tabs show,
the composer covers the rest, and even its Expand button cannot be tapped. The rules are
right for a phone without the keyboard; there is no room for all of them above it.

Options weighed:
- A (taken): a field of the card taking the focus on a phone expands the card, the mode
  its Expand button already has, and on a phone an expanded card also hides the
  session's tabs and the Team row. One focus handler and two CSS rules; no new state.
- B: a "keyboard mode" that guesses the keyboard from the visual viewport and hides the
  rest only while it is open. A heuristic that differs between iOS (the window does not
  resize) and Android (it does), and a new state to test on both.
- C: loosen the limits (the feed with no least height, the card above half). Cheap, but
  400 px still cannot hold the field, the buttons and the composer; it does not fix it.

## What Changes

- On a phone, in a session's chat, a field of the waiting card (a gate's comment, a
  question's own answer, a skip's comment) taking the focus expands the card, as its
  Expand button does; the focus stays in the field, so the keyboard stays open and the
  field shows within the card's list.
- On a phone an expanded card (expanded by a field or by its button, upright or
  sideways) also hides the session's tabs and the Team row: the card fills the page
  under the top bar.
- The card stays expanded when the keyboard closes, as after its Expand button; its
  Collapse button or Esc folds it, and it folds by itself when nothing waits.
- `docs/design/ui.md`: Phone layout, "The chat", and The waiting card, its expand
  paragraph, say the above.

## Scope

`web/src/WaitingCard.tsx` (the focus handler), `web/src/styles.css` (the section "Phone
layout"), `web/src/WaitingCard.test.tsx`, `tests/ui/test_phone.py`, `docs/design/ui.md`,
CHANGELOG.md.

## Out of scope

- Needs you on a phone: the page scrolls as a whole, and the field and the buttons can be
  scrolled to with the keyboard open (checked in the same browser); the card there keeps
  its behaviour.
- The keyboard opened from the composer: the human writes to the supervisor and the card
  yields its room to the feed and the composer; that the composer then lies over the
  card's tabs is a separate defect (BACKLOG.md, added by the developer).
- A computer, a tablet, a narrow computer window: no phone rule applies to them.
- Guessing whether the keyboard is open (option B): turned down for its heuristic.
- Folding the card by itself when the field loses the focus: a tap on Approve after
  typing would fold the card first and move the button from under the finger; the human
  chose that the card stays expanded.

## Acceptance criteria

- AC-1: On a phone (Chromium with a touch screen, 402×874), a gate waiting in the
  session's chat: a tap on the gate's comment field expands the card, the field keeps
  the focus; with the visible part of the window 400 px (a fake visual viewport), the
  field and Approve / Reject lie wholly within it, and the session's tabs and the Team
  row are not shown.
- AC-2: The same with a question's own answer: a tap on Other… expands the card, its
  field focused, and the field and "Send answer to …" lie within the visible 400 px.
- AC-3: When the visible part grows back (the keyboard closes) the card stays expanded;
  Collapse the card brings it back above the composer and the session's tabs and the
  Team row show again.
- AC-4: Expanded by its button on a phone, the card hides the session's tabs and the
  Team row too; on a computer an expanded card shows them as before, and focusing a
  field of the card on a computer does not expand it; on Needs you a field's focus does
  not expand the card on a phone either.
- AC-5: By hand on an iPhone in Safari (the task's screenshot): tapping a gate's comment
  shows the field and the buttons above the keyboard, and a comment can be typed and
  sent with Approve or Reject.
- AC-6: `make lint`, `make web`, the unit tests and `uv run pytest -m ui
  tests/ui/test_phone.py` pass; CI is green on the pull request's last commit.

## Impact

- Web UI only: no API, schema, MCP or CLI change. A fix: patch level; CHANGELOG.md gets
  a line under `### Fixed` of `## 0.43.0 (unreleased)`, the version not bumped here.
- Living specs: `phone-layout` (two requirements added, a field expands the card and an
  expanded card hides the session's tabs and the Team row; "On a phone the composer stays
  at hand" modified, its expanded card's scenario) and `chat-question-card` ("The
  expanded card covers its page's area, not the window" modified: but on a phone).
