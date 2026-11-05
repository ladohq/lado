# LAD-199 stopped-question-notice: review report

Pull request #215 `fix/lad-199-stopped-question-notice` → `main`. Scale: tweak, review depth:
precision, widened to a full pass of the lenses for the changes in `runs.resume` and the stop
path. Head reviewed: `51ad48b4` (= the remote head). A question a stop closes gets its own
state `stopped` and the card "Closed: the session stopped"; the resumed supervisor gets one
message from LADO with the questions left unanswered, once; Stop's popover and `lado stop` say
how many open questions the stop closes. No schema migration, no MCP or CLI option change.
Delta: a new capability, `stopped-questions`, four requirements.

## Rounds

- **Round 1** (local, `931818bb..a3c5274e`): the lenses of spec, tests, silent failures,
  comments, types and a general one, read by hand. Found F1 and F2.
- **Round 2** (local, `a3c5274e..5829b629`): precision over the docs' fixes. F1 and F2
  resolved; new: F3.
- **External round 1** (Claude Code GitHub Action, range `931818bb..5829b629`, finished in
  37 s): no blockers; read every changed file of `src/`, `web/src/Question.tsx` and
  `SessionControl.tsx` (the risky code), not the tests, docs or openspec, and ran nothing.
  Found F4 and F5.
- **Round 3** (local, after the refused archive, `5829b629..51ad48b4`, one file, six lines):
  F6 resolved; a trial archive in a copy of `openspec/` validates. No new findings.

External rounds used: 1 of 1 (the tweak cap), so the external reviewer did not see
`51ad48b4`. It is of the same model family, so its "no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | `docs/design/ui.md` disagreed with the code: its list of question states lacked `stopped`, and it called the questions of `lado stop` `closed` | fixed in `5829b629`, docs only |
| F2 | minor | in `docs/cli.md` an insertion tore "Such a worker" from `spawn_worker(run=...)` | fixed in `5829b629`, docs only |
| F3 | minor | `docs/cli.md`: after F2's move "in that body" follows the sentence on the second message, while it means the body of `session resumed` | declined: wording only, the sense is clear from the context; left to the human at the merge gate, who approved without it |
| F4 | minor | external: `tell_questions` repeats the insert of `queue_message`, so a new column or default would not reach it by itself | declined: the insert and the mark in `answered_by` must share one transaction; left to the human at the merge gate, who approved without it |
| F5 | — | external: `state.py:1612` named as the migration's path | refuted: that line is `fail_resume`; the migration goes through `state.stop_session`, and every path gives `stopped` |
| F6 | important | integrator: the delta of the new capability had no `## Purpose`, so the archive wrote a placeholder and `openspec validate --specs --strict` failed (56 passed, 1 failed) | archive undone before any commit; fixed in `51ad48b4`, the spec's text only |

F6 passed rounds 1 and 2 because neither `openspec` check sees it: `validate <change>` does
not read Purpose, and `validate --specs` does not see a capability not yet archived.

## Checks

- CI on head `51ad48b4` (run 41982219802): 23 of 23 pass, `ci-ok` among them, with the smoke
  of every provider on Linux and macOS.
- On `51ad48b4`: `make lint` clean; `openspec validate stopped-question-notice --strict`
  valid; the trial archive's `openspec validate --specs --strict` 57 passed, 0 failed.
- On `a3c5274e` (only docs and the spec's text changed after it): `make test` 4814 passed, 7
  skipped; integration, two changed files, 13 passed; UI, two changed files, 59 passed; `make
  web` 62 files, 1164 vitest tests.
- The integration test of the container's stop (`LADO_CONTAINER=1`) run five times: 5 of 5
  passed, 2.5 to 3.05 s each.
- The order `session resumed`, the notice, the human's first message: seen in a temporary test
  outside the repository; the pull request holds no lasting test of the three together.
- Not run: `make test-live` (`src/lado/runtime.py` changed; `providers/`, `hooks.py`,
  `mcp_server.py`, `agent_env.py` and `tests/live/` did not); `make check` and `make
  test-integration` as a whole locally (excluded by the settings, CI covered them).

## Not established

- Why the analyst saw no resume within 4 seconds in the container's run: it does not reproduce
  here, and the scenario was not run in real Docker.
- The integration test of the container's path does not show that the supervisor read the
  notice; reading is checked on the path of `lado stop`, the mechanism past it is shared.
- A question already `closed` before the stop (the supervisor's CLI crashed, then `lado stop`
  and `lado start`) is not told to the new supervisor: as AC-3 says, and left to the human. The
  same may hold when tmux falls or in `_kill_for_migration`, if the end hooks get to run; not
  checked.
- A manual downgrade: with no migration an old server meets `stopped` rows its `Literal` does
  not know, and the session's chat probably answers an error. From reading the code, not run.

Found on the way: `lado server stop` by hand in the container stops every session of its
`LADO_HOME`, already in BACKLOG.md (`42eb27d6`). For the settings: a Review trap on a new
capability's `## Purpose`, proposed to the human, who keeps `.lado/sdlc.md`.
