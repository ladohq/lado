# LAD-191 popup-test-waits-for-the-answer: review report

Pull request #238 `fix/lad-191-popup-test-waits-for-the-answer` → `main`. Scale: tweak, review
depth: precision. Head reviewed: `5a4d0fd8`. The flake of
`test_popup_opens_on_the_clients_attached_to_the_session`, a race in the test and not a defect of
`tmux.py`: the test waited for the answer file to exist and read it at once, while
`echo "$a" > file` creates the file empty and writes to it after. The wait now runs until the file
has content. Tests only: no API, schema, MCP, CLI or UI change, no CHANGELOG.md line. No delta.

## Rounds

1. Local, precision, `f3bb9a0f..5a4d0fd8`: no wide pass needed, the diff touches no business logic
   and no user data. The design and `tasks.md` were checked against the diff. No findings.
2. External 1, Claude Code GitHub Action: no blocker, one small remark, refuted (below). It did not
   read the openspec files, which are not risky and which the reviewer read. It is the same model
   family, so its verdict weighs less.

External rounds used: 1 of 1.

## The human's decisions

- **Question #4307, at the design:** the 20 runs in CI the task asked for are replaced by 20 local
  runs, the widened window and the pull request's green CI.
- **Gate `merge_ok`, approved** with no comment.

## Findings

No finding confirmed, local or external.

Refuted, external:

- **F1.** The `Found` line of the BACKLOG.md entry names the run's branch `lado/lado/task-lad-191`
  and not the pull request's, so the trace would be hard to find. Six entries of the file name a
  run's branch `lado/...` the same way, and this entry names LAD-191 too.

Found on the way:

- **The flake of `test_a_labelled_session_kept_after_its_command_gives_its_text_and_status`**, not
  related to this change. The developer measured 5 red of 40 with the fix and 5 of 40 without it;
  the reviewer did not repeat those runs. Its cause is not found and may lie in `tmux.pane_text`,
  on which the login window's text depends (`logins.py:313`). It has a P2 entry in BACKLOG.md
  (`5a4d0fd8`); no tracker task without the human's yes.
- **The description of LAD-191 in the tracker** still asks for 20 runs in CI; the human's
  replacement (#4307) is recorded in `proposal.md` only.

## Checks

| Check | Head | Result |
|---|---|---|
| The failing line in CI's log (PR #211, run 41818983454, attempt 1, `unit (3.13)`) | n/a | `tests/test_tmux.py:156`, `assert '' == 'approve\n'`, as the design says |
| AC-1: the diff | `5a4d0fd8` | one line changed in the tests, `src/` not touched |
| AC-2: a copy with 0.3 s between creating the file and writing, no fix | `5a4d0fd8` | 1 failed, `assert '' == 'approve\n'`, line 156 |
| AC-2: the same copy with the fix | `5a4d0fd8` | 1 passed; the copy lived outside the repository and is deleted |
| `make lint` | `5a4d0fd8` | exit 0, 1181 files |
| `make test` | `5a4d0fd8` | exit 0, 4823 passed, 7 skipped |
| `openspec validate popup-test-waits-for-the-answer --strict` | `5a4d0fd8` | valid |
| `openspec validate --specs --strict` | `5a4d0fd8` | 62 of 62 |
| A trial archive with `--skip-specs`, then the specs | `5a4d0fd8` | 62 of 62 |
| `echo`'s write in `dash` (the design's "one write") | n/a | 300 of 300 runs gave all 8 bytes in one read from a pipe |
| The same race in other tests | `5a4d0fd8` | none: `test_agent_env.py:113` reads no content, `test_telemetry.py:770` already waits for it |
| CI of the pull request | `5a4d0fd8` | 23 of 23 green, with `ci-ok`, integration, UI, container and smoke |
| A merge with `origin/main` | `5a4d0fd8` | no conflicts; `tests/test_tmux.py`, `BACKLOG.md` and `src/lado/tmux.py` did not change there |

The live tests were not needed: `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
`agent_env.py` and `tests/live/` did not change.

## Metrics

Rounds: 1 local, 1 external, 0 stand-in. Confirmed: 0 local, 0 external. Refuted: 0 local, 1
external. Findings in code changed by the cleanup lens: 0, it changed nothing.

## What was not checked

- AC-3 (20 runs under `-n auto`) was not repeated by the reviewer: it is the developer's result. The
  race's window is so narrow that such runs prove little; the ground is AC-2.
- `echo`'s single write was checked on `dash` only, not on macOS's `sh`. A split write would fail
  the test plainly at the `assert`, not pass it falsely.
- The integration, UI, smoke and container tests were not run locally: none of their files is in
  the diff, and all passed in CI.
- The other flake above may turn CI of this pull request or its merge red; by the project's rules
  the failed job is rerun alone.
