# LAD-225 dead-pane-test-waits-for-tmux: review report

Pull request #249 `fix/lad-225-dead-pane-test` → `main`. Scale: tweak, review depth: precision.
Head reviewed: `82c4c6cc`. The flake of
`test_a_labelled_session_kept_after_its_command_gives_its_text_and_status` comes from two races of
tmux 3.3a, not from `tmux.pane_text`: the test's command now exits only once its text is in the
pane, and a dead pane without a status gets a SIGCHLD from the test. Only `tests/test_tmux.py`,
BACKLOG.md and the change differ. No delta, no line in CHANGELOG.md.

## Rounds

1. Local, precision, `3f7222ff..82c4c6cc`: the test's diff by hand, the design's AC-1 to AC-5,
   `tasks.md`, the proposal's claims about the product against the code, the architecture against
   AGENTS.md. No breadth: the diff touches no product logic. Nothing found. External 1, Claude Code
   GitHub Action: no blocking findings, three small points; it read `tests/test_tmux.py`,
   BACKLOG.md, `tasks.md`, and `run` and `pane_text` of `src/lado/tmux.py`, not `proposal.md` or
   `.openspec.yaml`, which hold no risky code.

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Design:** "only the test", decided on 2026-11-07: no pause in the login wrapper, no nudge in
  `tmux.py`.
- **Gate `merge_ok`, approved** with no comment: F1 stays declined, and no live tests were asked
  for.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | external: no `assert` after the first wait, so a text that never showed fails the test later | declined: the exact assert of the text still shows the failure; a minor of the last round starts no new round |
| F2 | — | external: two waits of 10 s, 20 s at worst | refuted: the waits run one after the other, and 20 s adds up only in a test already failing |
| F3 | — | external: product code on `pane_dead_status` can still meet the race without a status, and BACKLOG.md has no entry for it | refuted: `remain-on-exit` is on login windows only (`src/lado/logins.py:58`), and `_status` reads the wrapper's file first, tmux's status only without one (`src/lado/logins.py:333`) |

## Checks

| Check | Head | Result |
|---|---|---|
| CI of the pull request, required `ci-ok` | `82c4c6cc` | green: run 42403651479, 23 of 23, smoke among them |
| `make lint` | `82c4c6cc` | clean |
| `make test` | `82c4c6cc` | 4845 passed, 7 skipped |
| `uv run pytest -n auto tests/test_tmux.py`, 25 times at a load average near 30 | `82c4c6cc` | 0 red of 25, 34 tests a run |
| `openspec validate dead-pane-test-waits-for-tmux --strict` | `82c4c6cc` | valid |
| `openspec validate --specs --strict`; trial archive with `--skip-specs` | `82c4c6cc` | 67 and 67 passed |
| `read _` under dash and `bash --posix` | `82c4c6cc` | works |

`make check`, `make test-integration` and `make test-ui` were not run locally: CI ran what they
hold. The live tests were not run: `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
`agent_env.py` and `tests/live/` did not change.

## Metrics

Rounds: 1 local, 1 external, 0 stand-in. Confirmed: 0 local, 1 external (F1). Refuted: 0 local, 2
external (F2, F3). Findings in code changed by the developer's cleanup: 0, as the cleanup changed
nothing.

## What was not checked

- The reviewer did not reproduce the cause in tmux: the numbers on bare tmux, the 700 runs of the
  wrapper and the probes (no SIGCHLD, no `read _`, `exit 4`) come from the proposal and the build
  report. Only the product's independence of tmux's status was read in the code.
- Why tmux misses the signal was not found; the human left it out of scope.
- The last line of a login window survives because Python's exit takes a moment, not by a
  guarantee, while the scenario "The last line survives the exit" and the docstring of `look`
  ("never lost") promise more. No loss in 700 runs; the pause in the wrapper was left out by the
  human's decision.
- Measured on Linux arm64 and tmux 3.3a only; the test was not run locally on macOS or another
  tmux version.

## Found on the way

Nothing.
