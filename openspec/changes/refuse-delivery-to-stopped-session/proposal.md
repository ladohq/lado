Task: LAD-227

## Why

`POST /api/sessions/{name}/messages` answers 500 when the session stops while the message is
delivered, and the composer shows "Internal Server Error" for a message the feed already shows.
Found among the console errors of the UI tests in LAD-224
(`tests/ui/test_stopped_session.py`, `test_the_bar_stands_in_the_composers_place`).

Cause, confirmed in the source: `runtime.hand_over` takes the queue (`state.take_pending`), then
types it (`tmux.send_text`). A stop between the two commits first (`_mark_stopped` marks the
session, its messages dropped, then kills tmux), so `send_text` raises `tmux.TmuxError`. Nothing
on the way catches it: `_deliver` knows only the queue's own refusal, and the server's `core` only
`LadoError` and `ArtifactError`. A stop a moment earlier gives a refusal already, through the end
of `_deliver`, but it reads `no running agent "supervisor"; running agents: ` with an empty list.

The task left open what a shared tmux server says. Checked by hand on tmux 3.3a:

- The stopped session was the server's last: `no server running on ...`.
- Other sessions run: `display-message` succeeds and prints nothing, `paste-buffer` fails with
  `can't find session: <name>`.
- A session whose name starts with the stopped one's runs: no error at all. tmux matches a target
  without `=` by prefix, so `paste-buffer -t lad:sup` pastes into `lad-224:sup`, and
  `new-window -t lad:` opens a window there. With `=` both fail with `can't find session`. A
  message of a stopping session can so land in another session's supervisor (`lad-154` and
  `lad-154-epic` are real session names), and the refusal could not be relied on.

Options weighed:

- A (taken): `_deliver` catches the `TmuxError` and asks whether the session ended: stopped by
  the database, or its tmux session gone (`loop.tmux_gone`, the session loop's own test). If it
  did, it refuses with a `LadoError`; if not, the error goes on. One place for every caller and
  provider; a real tmux failure stays a 500 and reaches the error journal. Cost: one more
  look at tmux, on a failure only.
- B: `core` turns every `TmuxError` into a 400. Fewer lines, but the human reads tmux's words
  with a socket path, every endpoint is touched, and real failures leave the journal.
- C: `hand_over` swallows the error and leaves the message to the sweep. A stop drops it anyway,
  so the human would take it for sent.

## What Changes

- A message whose delivery a session's end cuts off is refused with one sentence, which also
  replaces the empty `running agents:` refusal of a stopped session. It holds for each way in
  through `_deliver`: the human's message and replies, an agent's `send_message`, LADO's own.
- A real tmux failure on a session that still runs stays an error, as today.
- `tmux.send_text`, `tmux.new_window` and `tmux.capture` name the session and window exactly
  (`=`), as every other call of `tmux.py` does.

## Scope

In: `src/lado/runtime.py`, `src/lado/tmux.py`, their tests, `docs/design/agents.md`,
`docs/design/ui.md`, CHANGELOG.md, BACKLOG.md. No API model, schema or `web/` change.

## Out of scope

- A mark on the dropped message in the feed: decided by the human on 2026-11-07. The text stays
  in the composer and the refusal shows after Resume; `dropped` also covers a message whose line
  the agent got and whose body it did not read, where "not delivered" would be inexact.
- An agent's window gone in a session that runs: also a 500, but only until the loop's window
  check drops the message and tells. Another scenario, with its own outcome: a BACKLOG entry.
- The 500 of `tmux.TmuxError` from `start_session` (BACKLOG, the API's refusals): no delivery.
- Text for the refusal per caller: an agent reads the human's sentence too, which is rare and
  true; a stopping session's agents are ending.

## Impact

Patch-level fix: a line under `### Fixed` of `## 0.45.0 (unreleased)`. Works the same for every
provider: nothing below `runtime.py` knows one. The BACKLOG entry "A message sent as the session
stops answers 500" goes. "A traceback in hooks.log when the tmux server is gone at an agent's end"
goes too, if the unit test of task 1.5 shows `_tell_lead` now ends quietly.
