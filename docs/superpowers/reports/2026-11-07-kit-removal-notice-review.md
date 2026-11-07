# LAD-228 kit-removal-notice: review report

Pull request #244 `fix/lad-228-kit-removal-notice` → `main`. Scale: tweak, review depth: precision.
Head reviewed: `ac4c4ab8`. In the window Remove <kit>? the line about the running sessions takes
`.kit-warning` and becomes a warning notice, in both themes, its words unchanged; `.kit-danger`
goes. No server, API, schema, MCP or CLI change. Delta: 1 requirement modified in `notices`.

## Rounds

1. Local, precision, `origin/main...ac4c4ab8`: the diff read by hand against the spec, `tasks.md`
   and the design. No finding. No breadth pass: the diff touches no logic, no user data and no code
   of earlier rounds.
2. External 1, Claude Code GitHub Action: no blocker, one minor (F1), refuted. It did not read the
   three files of `openspec/changes/kit-removal-notice/`, which are not risky and which the local
   round read. It is the same model family as the kit's agents and ran no tests.

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Answer #4491:** a warning, not the error of the task's text, with the mock-up "Warning notice":
  nothing has failed when the line shows, and red stays for a real refusal of Remove.
- **Gate `merge_ok`, approved** on `ac4c4ab8`.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | — | external: `docs/superpowers/reports/2026-11-07-session-screen-qa-fixes-review.md:95` still names the defect `.kit-danger` | refuted: that is the review report of LAD-224 (PR #240), a record of what was found then, not a description of the code |

Confirmed: 0 local, 0 external. Refuted: 0 local, 1 external. Declined: 0. Findings in code changed
by the developer's cleanup: 0, as the cleanup changed nothing.

## Checks on `ac4c4ab8`

| Check | Result |
|---|---|
| `make lint` | clean |
| `uv run pytest -m ui tests/ui/test_kits_page.py tests/ui/test_session_list.py -n auto` | 19 passed |
| `openspec validate kit-removal-notice --strict` | clean |
| `openspec validate --specs --strict` | 67 passed |
| Trial archive in a copy, then `openspec validate --specs --strict` | 67 passed |
| CI | `ci-ok` green at the first attempt: unit, integration (6 cells), UI (2), JS, container (2) |
| Smoke | skipped by CI: the pull request is wholly within the skip list |

## Not checked

- That the new test was red before the change comes from the developer's output (`{'ground': False,
  'border': '1px', 'icon': 'none'}`); it matches the old `.kit-danger` rule read in the diff, and
  the reviewer did not reproduce it.
- `make test` and `make web` were not run by the reviewer; the developer reported 4826 passed, 7
  skipped and 1537 tests on `8614cfcb`, and CI covers the unit tests on `ac4c4ab8`.
- `make test-smoke` and `make test-live` were not run. The diff does not change `providers/`,
  `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or `tests/live/`, so no live run was
  needed before the merge.
- No test covers the window with both the running and the stopped sessions' lines. The mock-up has
  that case and the two lines' markup is independent, so the risk is low.

## Notes

- `CHANGELOG.md` stays as it is: the unreleased item "Errors and warnings look like what they are"
  already says the kit windows' warnings are notices, and this change makes it wholly true.
