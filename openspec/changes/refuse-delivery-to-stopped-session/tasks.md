## 1. The refusal

- [ ] 1.1 `tests/test_runtime.py` (unit, written first, red): `tmux.send_text` replaced by a
  function that stops the session, then raises `TmuxError`: `write_as_human` to the supervisor and
  to a worker, and `answer_questions`, raise `LadoError` with the sentence; the message is dropped.
- [ ] 1.2 `src/lado/runtime.py`: the sentence, the helper "the session ended", the `try` in
  `_deliver` and the check in `_to_running` (design.md D1 to D3).
- [ ] 1.3 `tests/test_runtime.py` (unit): the session stopped between the queueing and the
  hand-over gives the same sentence, with no `running agents`; tmux gone without a stop
  (`has_session` False) too; `TmuxError` with the session there, and `TmuxMissing`, go on
  unchanged; a stopped agent of a running session keeps `no running agent`.
- [ ] 1.4 `tests/test_server_messages.py` (unit, the API): `POST .../messages` and `.../answers`
  with a stop during the delivery answer 400 with the sentence in `detail`.
- [ ] 1.5 `tests/test_runtime.py` (unit): `_tell_lead` with the tmux server gone ends without an
  error, the message stays queued. When it passes, the BACKLOG entry "A traceback in hooks.log when
  the tmux server is gone at an agent's end" goes in task 4.3.

## 2. Exact targets

- [ ] 2.1 `tests/test_tmux.py` (real tmux, written first, red): on one server with `lad-1` running
  and `lad` gone, a window of the same name in both: `send_text`, `new_window` and `capture` to
  `lad` raise `TmuxError`, nothing is typed into `lad-1`, it has no new window.
- [ ] 2.2 `src/lado/tmux.py`: `send_text`, `new_window` and `capture` name the target exactly
  (design.md D7). `test_tmux.py` still passes for a running session.

## 3. End to end

- [ ] 3.1 `tests/integration/` (fake agent, real tmux, `-m integration`), around the real
  `tmux.send_text` a wrapper that stops the session first: a session alone on its tmux server
  (`no server running`), and one sharing it with a session whose name starts with its own (`can't
  find session`, and the other session's agent gets nothing). `write_as_human` is refused with the
  sentence in both; the session stays stopped and can be resumed.
- [ ] 3.2 `web/src/Composer.test.tsx` (unit): a send refused with a 400 keeps the text and the
  files and shows the `detail`, unless a test does already; folded and unfolded again it shows
  both. No change to `web/src` is expected: a failure here is a finding, not a task to widen.
- [ ] 3.3 The regression run: `make lint`, `make test`, the changed integration file with
  `-m integration`, `openspec validate refuse-delivery-to-stopped-session --strict`, and the trial
  archive of `.lado/sdlc.md`, Checks. `tests/ui/test_stopped_session.py` with `-m ui` shows no 500
  in the console.

## 4. Documents

- [ ] 4.1 `docs/design/agents.md`, where messages are delivered: the refusal and what counts as a
  session's end; the exact targets, if tmux targets are described there.
- [ ] 4.2 `docs/design/ui.md`, A stopped session's bar: a message refused by a stop stays in the
  folded composer and shows its refusal after Resume.
- [ ] 4.3 CHANGELOG.md, `## 0.45.0 (unreleased)`, `### Fixed`: one item. BACKLOG.md: take out "A
  message sent as the session stops answers 500" (and the entry of 1.5 if it passed); add the
  window gone in a running session, with `Size:`, `Why here:` and `Found:`.
