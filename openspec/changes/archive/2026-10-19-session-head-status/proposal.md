Task: LAD-108

## Why

Symptom (the task's screenshot, a phone): the session `cloud` has a question waiting and
its agents idle. The session list puts it under **Needs you**, in the human's orange, with
no dot; its Running row, had nothing waited, would show the idle ring. The session's head
shows a full green dot. On a phone the list is not on the screen, so the head is the only
place the human could learn the session's state, and it says the wrong thing.

Cause: the head's dot (`StatusDot`, `web/src/Sessions.tsx`) is drawn from
`SessionInfo.status` alone, whose `running` only means the session's tmux and loop are
alive; the list's mark is drawn from the group (`waits`: something waits for the human)
and, in Running, from the agents' work (`tracked`, `workWord`: `SessionInfo.busy`). Two
rules read the same session two ways, and the head's green full dot is the very mark the
list uses for "agents working".

## What Changes

- One rule in the web UI, a session's mark (`sessionMark` in `web/src/Sessions.tsx`),
  says what a session is in: `needs-you`, `working`, `idle`, `stopped`, `tmux_gone` or
  `loop_down`, with the words that name it. The list's row, the strip's icon, the
  session's card, the head on a computer and the head on a phone all take it; none keeps
  a rule of its own.
- The head's dot shows the list's mark: needing the human, an orange diamond (the shape
  of a waiting agent in the team's chips); working, the list's full green dot with its
  pulse; idle, the list's muted ring; stopped and trouble as before.
- The dot's tooltip and accessible name say the card's words: `needs you · 1 question`,
  `running · 2 of 3 agents working`, `running · idle · 3 agents`; stopped and trouble as
  before. On a phone the session's details sheet opens with the same words and the run
  time.
- `docs/design/ui.md` (Sessions, Session head, Phone layout) says the head's mark is the
  list's.

## Scope

`web/src/Sessions.tsx` (the rule and its users), `web/src/styles.css` (the head's marks),
the vitest tests of the list and the head (`web/src/Layout.test.tsx`,
`web/src/SessionDetails.test.tsx`), a UI e2e test on a phone's width
(`tests/ui/test_phone.py`), `docs/design/ui.md`, CHANGELOG.md.

## Out of scope

- A state field in the server's API (`SessionInfo.state`): the UI already gets every fact
  it needs (`status`, `busy`, `waiting`) from the same feed, so a server field would only
  move the rule and change the API, the generated types and `lado ls` for nothing seen.
- A second dot in the head (the old "running" one beside the activity one): two marks side
  by side read as two things, and the list has one.
- The status word in the phone's top bar: the line has no room (the title is already cut);
  the word is in the dot's tooltip and the details sheet.
- The marks themselves in the list, the strip and the team's chips: they stay as they are;
  only the head follows them.
- The known limits of `busy` (a Claude agent interrupted with Esc stays busy, BACKLOG.md):
  the head now shares them with the list, which is the point.

## Acceptance criteria

- AC-1: For each state (needs you, working, idle, stopped, tmux gone, loop down) the
  session's row (or the strip's icon) and its head show the same mark, both drawn from
  `sessionMark` (vitest).
- AC-2: With a question waiting and the agents idle (the screenshot's case), the head's
  dot is the orange diamond named `needs you · 1 question`, not a green dot.
- AC-3: A working session's head dot pulses as the list's working dot; an idle session's is
  the muted ring; their names are `running · 2 of 3 agents working` and
  `running · idle · 3 agents`.
- AC-4: On a phone (390 px, coarse pointer) the top bar shows the mark of the session's
  state, a tap on it shows its words, and the details sheet's state line starts with the
  same words (vitest; UI e2e in Chromium).
- AC-5: Stopped, tmux gone and loop down look and read in the head as before.
- AC-6: `make lint`, `make test`, `make web` and the changed UI tests pass; CI is green.

## Impact

- `web/` only, plus the UI document and CHANGELOG.md. No API, schema, MCP or CLI change.
  A fix users see: a CHANGELOG.md line, the patch.
- The parallel task LAD-109 edits the phone layout (`styles.css`'s last section,
  possibly `Sessions.tsx`'s `PhoneHead`): a conflict at merge is likely small.

## Decisions for the record

- Scale hotfix: a defect with a clear symptom and a known cause; review by precision.
- The rule lives in the UI, next to `waits` and `tracked`, which it replaces as the one
  place the list's and the head's marks come from: the facts are already in
  `SessionInfo`, and a server field would be a second home for the same rule.
- The head's marks reuse the list's classes (`dot`, `activity-working`, `activity-idle`)
  and the waiting agent's diamond, so the look has one definition; `session-dot` keeps
  its size and place in the top bar.
- Test layers: vitest for the rule and for every state of the row and head (jsdom sees
  the classes and names); one UI e2e on the phone's width for what needs a browser (the
  dot in the one-line top bar, the tap's tooltip).
