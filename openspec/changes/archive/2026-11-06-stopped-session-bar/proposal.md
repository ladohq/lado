Task: LAD-196

## Why

Symptom (audit of LAD-189, finding F17): a stopped session's empty feed says "No messages yet.
Write to the supervisor below." over a disabled composer. The only way on is an icon ▷ without a
word in the head. The terminal shows `closed: session "…" is stopped` with Reconnect, which can
give nothing.

Cause: a stopped session has no state of its own on the page. Each part shows its running look with
one flag: the composer is disabled, the head swaps its icons, the panel tries a socket and reports
the close. Nothing says what the session is or leads the human on.

Options weighed:

- A: new words in the running look (a placeholder, a tooltip, a label on the icon). The least code,
  but the disabled composer stays where the way on should be, and Reconnect stays.
- B (taken, LAD-189 spec §5, frames g5-1440 and g5-term): the composer gives way to a bar with
  Resume session, and the feed, the head, the team and the terminals each get a stopped look. It
  touches six components, and all go through the one Resume action that exists.
- C: a stopped session as a separate read-only page. Clear, but a second layout of the tabs to keep
  true to the first, for a state that needs no other data.

## What Changes

- On Activity the composer gives way to a bar: "This session is stopped", "Its branches, runs and
  history are kept", and the primary button Resume session.
- The empty feed of a stopped session says "Nothing was said in this session." when it shows all
  messages, and "No messages with you. Messages between agents are hidden." under Yours. The second
  text goes beyond the spec: the human's decision after ui-review's finding F1, since the first
  would be false in a session where only agents talked.
- The head shows only Forget on Activity. On every other tab, Agents too, a secondary Resume with
  its word stands before it, at any width.
- A phone's Activity loses the word Team; its toggle gets the words Messages between agents.
- A stopped session's terminals start folded, and nothing of that is stored. After Resume they
  return to the human's choice.
- An opened terminal of a stopped session says "Agent not running — resume the session to start
  it", with no socket, Reconnect or Take control.

The change is a feature users see and goes under `## 0.45.0 (unreleased)`, whose minor is already
bumped: no further bump. No API, schema, MCP or CLI change.

## Acceptance criteria

- AC-1. A stopped session's Activity shows the bar in the composer's place at 1440, 768 and 390,
  empty or not; above a phone it is at least 52 px high, on `--panel` with a `--line` frame and a
  radius of 8. It repeats no stop time.
- AC-2. Resume session opens the Resume window, the same action as the head's Resume. Once the
  session runs, the composer stands in the bar's place with its text as it was.
- AC-3. With the connection lost, both Resume buttons are disabled and say "Waiting for connection"
  in a tooltip.
- AC-4. The empty feed says the texts above by its filter, centred in `--muted`. A feed with entries
  and a running session's empty feed do not change.
- AC-5. On Activity the head has Forget alone. On Agents, Flows and Artifacts it has Resume with its
  word at 14 px, then Forget, at 1440, 768, 390 and 320, with no sideways scroll; a long title is
  cut, not the button. A session whose tmux session is gone keeps its icons.
- AC-6. No team shows in the head. On a phone no word Team and no chips show, and the toggle shows
  its words and its pressed state.
- AC-7. A stopped session's terminals are folded whatever is stored, and `lado.terminals` and the
  column opened last do not change, also when the human opens or folds them. After Resume, or in
  another session, the stored choice shows.
- AC-8. An opened terminal shows the text in mono 13 on `--term-ground`, under `Viewing`, with no
  Reconnect, no Take control and no socket. A running session's closed terminal keeps Reconnect.
- AC-9. On a phone held upright the button stands under the text at full width, 44 px high; held
  sideways the bar is one row.
- AC-10. `make web`, `make test`, `make lint` and `make test-ui` pass; CHANGELOG.md and
  `docs/design/ui.md` are updated in the pull request; ui-review checks the build against g5-* and
  the dark theme.

## Out of scope

- A session whose tmux session is gone (`tmux_gone`): its composer, head and Reconnect stay. The
  spec describes `stopped` only, and that session may still have live agents.
- Resume in one click: it would need a request of its own and lose the window's choice of kits,
  provider and mode. The human's decision.
- Agents on the strip and a count on the Agents tab, as frame g5-1440 shows: a stop deletes the
  agents, and showing them would need data that no longer exists. The human's decision.
- The running session's text "No messages yet. Write to the supervisor below." under Yours: the
  spec asks nothing of it.
- A phone's way to open a terminal of a stopped session: no chip is left to open it, and it could
  only say that the agent is not running.
- Feedback for Quote in a stopped session: the quote waits in the hidden composer and shows after
  Resume (`design.md`, D3).

## Impact

- `web/src/`: `SessionControl.tsx`, `Sessions.tsx`, `Chat.tsx`, `Composer.tsx`, `Agents.tsx`,
  `columns.ts`, `Terminals.tsx`, `styles.css`.
- Tests: vitest and `tests/ui/`; the tests that press `Resume…` in the head on Activity move to the
  bar or to another tab.
- Docs: `docs/design/ui.md`, CHANGELOG.md.
