# LAD-296 multiline-paste-test-waits-for-file: review report

Pull request #343 `fix/lad-296-multiline-paste-test` → `main`. Scale: tweak, review depth:
precision. Head reviewed: `16392615`. `test_send_text_pastes_multiline_text` creates `out.txt`
before its tmux window starts, so the wait loop no longer fails at once with `FileNotFoundError`
when the window's shell starts late. Tests only: no `src/`, `web/`, schema or API change, no
CHANGELOG.md line, no delta.

## Rounds

1. Local, precision and a check against the design, `3e886a20..16392615`. External 1, Claude
   Code GitHub Action: no findings; files read `tests/test_tmux.py` and `tasks.md`, not read
   `proposal.md` and `.openspec.yaml` (not code, read by the reviewer); no risky code unread.

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Gate `merge_ok`, approved** with no comment.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| N1 | — | external, no action asked: two `read_text()` calls read the file twice | refuted: the second read is the assertion after the loop, by design (`tests/test_tmux.py:48-50`) |

## Checked against the code

- AC-1: `out.touch()` comes before `tmux.new_session`; the test's diff is that one line.
- AC-2: the race reproduced by the reviewer with a copy of the test in a temp folder, window
  command `sleep 1; cat > out.txt`, its own tmux socket: without `touch` `FileNotFoundError`,
  with it a pass. Nothing committed.
- AC-3: from the build report (50 of 50 alone, 3 × 34 passed for the file); the reviewer's own
  run: 1 passed.
- AC-4: `make lint` exit 0. CI: the unit jobs green on the first attempt.
- Every task of `tasks.md` checked; `openspec validate multiline-paste-test-waits-for-file
  --strict` valid.

## Checks

| Check | Result |
|---|---|
| `make lint` | exit 0 |
| The changed test, `-n0` | 1 passed |
| `openspec validate multiline-paste-test-waits-for-file --strict` | valid |
| CI run 44605795767, attempt 1 | 25 passed, `ui (3)` failed (unrelated flake, below) |
| CI run 44605795767, attempt 2 (`gh run rerun --failed`) | 27 of 27 passed, `ci-ok` green |

## Metrics

Rounds: local 1, external 1, stand-ins 0. Confirmed: local 0, external 0. Refuted: external 1
(N1). Findings in code changed by the developer's clean-up: 0.

## Found on the way

- Flake: job `ui (3)`, step `uv run pytest -m ui -n 2 --shard 3/4`, test
  `tests/ui/test_launch.py::test_on_a_phone_every_field_and_button_of_the_window_is_a_44_px_target[chromium]`
  (line 1371): a click 5 px right of the kit chip's drawn × did not remove the chip. The diff
  touches neither the UI nor `tests/ui/`; it passed on the rerun. Left to the human for
  BACKLOG.md or the tracker.

## Not verified (residual risk)

- Integration, UI, smoke and container tests were not run locally: the change does not touch
  them, and CI ran them green. `make test-live` was not run: at release only.

No change in `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
`tests/live/`.
