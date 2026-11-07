## 1. The test

- [ ] 1.1 `tests/test_tmux.py` (unit layer, real tmux, as the rest of the file):
  `test_a_labelled_session_kept_after_its_command_gives_its_text_and_status` runs
  `printf 'one\n\nlast words\n'; read _; exit 3`; it polls `tmux.pane_text` until `last words`
  shows (at most 10 s), sends Enter with `tmux.run("send-keys", ...)`, then polls `_dead`. While
  the row is `["1", ""]` it sends the server a SIGCHLD (its pid from `#{pid}`), so one deadline of
  10 s covers the wait. The asserts stay: `["1", "3"]`, and the text without tmux's own line. A
  comment says why: tmux may miss the exit until the next SIGCHLD, and drops unread output when
  the exit comes first. Check: the test passes alone with `-n0`.
- [ ] 1.2 Proof against the flake: `uv run pytest -n auto tests/test_tmux.py` 40 times in a row,
  with the exit status of each run read, none red (before: about 5 red of 40). Report the count
  in `build-report`.

## 2. Backlog

- [ ] 2.1 BACKLOG.md: remove the entry "test_a_labelled_session_kept_after_its_command_gives_its_text_and_status
  fails under load". Check: `grep` finds the test's name nowhere in BACKLOG.md.

## 3. Checks

- [ ] 3.1 `make lint`, `make test`.
