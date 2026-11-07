Task: LAD-225

## Why

Symptom: `tests/test_tmux.py::test_a_labelled_session_kept_after_its_command_gives_its_text_and_status`
fails in about one run of the file in eight under `-n auto` (2026-11-06, tmux 3.3a, 16 workers:
5 red runs of 40 with the fix of LAD-191, 5 of 40 without it; 15 of 15 green alone with `-n0`).
It fails in two shapes: `assert ['1', ''] == ['1', '3']` after the whole 10 s, and
`assert '' == 'one\n\nlast words'` with the status there.

Cause, confirmed on 2026-11-07: both shapes are tmux's, and the product is right. Both were
reproduced on bare tmux 3.3a (Debian 3.3a-3, Linux arm64, this container), with no LADO code, by
a script that runs the test's command on its own server; `tmux.pane_text` only returns what tmux
holds.

- **No status.** tmux sees the end of the pane's output and lists the pane dead, but does not act
  on the command's exit: the command stays a zombie, and tmux draws no "Pane is dead" line. The
  status comes with the next SIGCHLD: `kill -CHLD <server>` gave status 3 in 7 of 7 such panes.
  On an idle machine 4 to 7 runs of 300 on a new server, 0 of 300 on one already running; under
  24 busy loops 6% to 41% of runs, on a running server too (22 of 200). A pause in the command
  before its exit does not help (2 of 300 with 0.3 s). Why tmux misses the signal was not found.
- **No text.** When tmux learns of the exit before it read the rest of the output, it closes the
  pane and the unread bytes go: `window_pane_destroy_ready` looks at the unread bytes only with
  `pipe-pane` on (tmux 3.3a, `window.c`). The test's command prints and exits at once: 4 of 250
  under load, and 0 of 250 with a pause of 50 ms before its exit.

The product does not depend on either. `remain-on-exit` is used by login windows only, and they
run their command under the wrapper `lado.logins`, which writes the exit status to a file
(LAD-168, for this same loss) and takes a moment to end, so tmux reads the output first. The real
wrapper under load, 700 runs: tmux gave no status in 255, and the file's status and the text were
right in all 700. `tests/integration/test_provider_logins.py` covers that way with real tmux.

The test's command is the worst case of both races, a case no LADO window runs.

Options weighed:

- A (taken, the human's choice on 2026-11-07): the test drives the two races out. Its command
  waits for a line, the test sends it only once the text is in the pane, and a dead pane without
  a status gets a SIGCHLD from the test. The test keeps checking status 3 and the text without
  tmux's line. Cost: the wrapper's margin rests on Python's exit taking a moment, not on a
  guarantee; no loss in 700 runs.
- B: A, and the wrapper pauses about 0.1 s before its exit, so the scenario "The last line
  survives the exit" does not rest on that margin. Left out: no loss was seen without it, and no
  test can show what it changes.
- C: `tmux.py` sends the server a SIGCHLD when it sees a dead pane without a status. Left out: a
  second source of the exit status beside the wrapper's file, and it does not save the text.

## What Changes

- The test's command waits for a line before it exits; the test sends that line once the text is
  in the pane, and gives a dead pane without a status a SIGCHLD. A comment names both tmux races.
- BACKLOG.md loses the entry of this flake.

No behaviour changes, so the change has no delta. Archive it with `--skip-specs`.

## Scope

In: `tests/test_tmux.py`, BACKLOG.md. No change under `src/`, `web/` or the docs.

## Out of scope

- A pause in the login wrapper (option B) and a nudge in `tmux.py` (option C): see above.
- Finding why tmux misses the signal, and a report to tmux: LADO's windows do not depend on it,
  and the task asks for the cause of the flake, which is found.
- A new test of a login window with real tmux: `tests/integration/test_provider_logins.py` has
  them, and a test of a loss seen in 0 of 700 runs could show nothing.

## Impact

No release line: the change touches tests and BACKLOG.md only, so no minor or patch bump of its
own, and CHANGELOG.md stays as it is. Neutral core: no provider is involved. Measured on Linux
arm64 only; the test holds on any platform, since it needs neither race to pass.
