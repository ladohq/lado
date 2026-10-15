# LAD-68 visible-one-line-text: review report

Pull request #70 `fix/lad-68-hidden-characters` → `main`. Scale: tweak, reviewed for
precision over the diff, at most one external round. Head reviewed last: `c0c71da` (= the
remote head); the archive commit follows it. `runtime.py` changed (`set_title`,
`_check_summary`, `ask_human`'s choices, `_human_text`): only error texts and the cleaning
of one-line forms, no delivery; `providers/`, `hooks.py`, `mcp_server.py`, `agent_env.py`
and `tests/live/` did not change. The reviewer judged live tests not needed before the
merge and left the call to the human.

## Rounds

- **Round 1, local** (precision over `origin/main...a5dbd01`: spec, tests, comments and
  docs, general, and the architecture against AGENTS.md): F1, F2.
- **Round 2, local** (precision over `a5dbd01..c0c71da`): F1 and F2 resolved; F3 new,
  minor.
- **Round 1, external** (Claude Code GitHub Action, request 19:38:04Z, answer 19:39:35Z,
  on `c0c71da`; it read the code and ran no tests): E1–E4, all minor, confirmed and
  declined. The triage is answered on the pull request. The external reviewer is of the
  same model family, so its "nothing blocking" weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (spec) | `flow_start`'s `human_language` was checked by its own copy (`"\n" in language`), not by `lado.text`, against the spec's "no other copy" | confirmed | important | fixed in `c0c71da`, test `tests/test_runs.py::test_a_language_with_a_hidden_character_is_refused` seen red first |
| F2 | 1 | local (docs) | added lines of `docs/design/ui.md` and `AGENTS.md` past the wrap width | confirmed | minor | fixed in `c0c71da` |
| F3 | 2 | local (docs) | the same for lines `c0c71da` added to the openspec change's documents | confirmed | minor | declined: looks only, archived documents |
| E1 | ext. 1 | external | a title (or the first line of a human's message) of a lone U+200D passes and looks empty | confirmed | minor | declined: the spec keeps U+200D visible on purpose; it takes deliberate input |
| E2 | ext. 1 | external | lone surrogates (category Cs) are not hidden, and SQLite fails on them | confirmed | minor | declined: older than the change (the same on main), outside the approved Cc/Zl/Zp/Cf rule; proposed for BACKLOG.md |
| E3 | ext. 1 | external | a loop limit's cancel reason is not cut | confirmed | minor | declined: older than the change; the whole text goes to the supervisor |
| E4 | ext. 1 | external | no test of `_answer_note` for a note both cleaned and cut | confirmed | minor | declined: the condition `note != f"{outcome}: {comment}"` covers it by construction |

## Checks

- On `c0c71da`: `make lint` 0; `make test` 3314 passed; `openspec validate --specs
  --strict` 28 passed, `visible-one-line-text --strict` valid; CI run 38795281012 all
  green, `ci-ok`, the smoke and the container jobs included.

## Not checked (residual risk)

- Integration, UI, smoke and container tests were not run locally; CI ran them, green.
- `make test-live` was not run.

## Found on the way

- Lone surrogates (Cs) from an MCP call's JSON reach SQLite and fail with
  `UnicodeEncodeError` (`'a\ud800'`), on main too. Proposed for BACKLOG.md: refuse Cs in
  one-line texts and bodies at the MCP tools' input (P3, Size: S).
