# LAD-71 migration-backup: review report

Pull request #58 `fix/lad-71-db-backup-before-migration` → `main`. Scale: tweak, reviewed
for precision, but round 1 for breadth as the diff touches the human's data (`lado.db`);
at most one external round. Head reviewed last: `9fb3de6` (= the remote head); the
archive commit follows it. `providers/`, `hooks.py`, `mcp_server.py`, `agent_env.py` and
`tests/live/` did not change; `runtime.py` changed only on the migration's path
(`_migrate`, `stop_session`, `stop_all`: the line and the failure's message), so live
tests are not needed before the merge in the reviewer's view.

## Rounds

- **Round 1, local** (breadth over `81494b8..cacc790`): F1, F2, F3.
- **Round 1, external** (Claude Code GitHub Action, request comment 6190633302, answer
  "Claude finished" 11:09:47 UTC, triage comment 6190659329): E1, E2, E3. The external
  reviewer is of the same model family, so its "nothing blocking" weighs less.
- **`merge_ok` rejected**: the supervisor's item M1 (after `docker compose pull` the image
  before has no name to go back to), with E2 and F1.
- **Round 2, local** (precision over `cacc790..d27a645`): M1, E2, F1 resolved; new G1,
  G2, G3.
- **Round 3, local** (precision over `d27a645..9fb3de6`): G3 and G1 resolved; new H1, H2.

External rounds used: 1 of 1. The fixes of rounds 2 and 3 (`lado:previous`,
`CONTAINER_UPDATE`, `.env`) were seen by the local reviewer only.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (comments) | D4 of `design.md` says `runtime` journals the error; `cli.main` does | confirmed | minor | fixed in `226e8cd` |
| F2 | 1 | local (spec) | the rule "keep the error in the journal" does not exempt `lado uninstall`, which journals nothing | confirmed | minor | declined: uninstall's rule as before |
| F3 | 1 | local (silent failures) | after a failed migration uninstall says "run lado uninstall again", which fails the same way | confirmed | minor | declined: a rare edge; before, it was a traceback |
| E1 | ext. 1 | external | the backup's mode is wider than `lado.db`'s | refuted | — | dropped: SQLite makes both alike |
| E2 | ext. 1 | external | a failed `unlink` of an earlier backup stops the migration | confirmed | minor | fixed in `d27a645` with `test_state.py::test_an_earlier_backup_that_cannot_be_removed_does_not_stop_the_migration` |
| E3 | ext. 1 | external | `after` is always `SCHEMA_VERSION` | refuted | — | dropped: the rollback to `before` is right |
| M1 | `merge_ok` | human | after `pull` the image before has no name (`<older>`) | confirmed | important | fixed in `226e8cd`: `lado:previous`; container test `test_the_compose_headers_steps_put_the_backup_back` |
| G3 | 2 | local (one source of truth) | LADO's own update hint in a container (`update.CONTAINER_UPDATE`) lacks the `lado:previous` step | confirmed | important | fixed in `9fb3de6`; `test_docker.py::test_lados_own_update_hint_is_the_compose_headers_update` keeps it equal to the header's commands |
| G1 | 2 | local (comments) | the header does not say to keep `LADO_IMAGE=lado:previous` after going back | confirmed | minor | fixed in `9fb3de6` with `test_the_compose_header_says_to_keep_lado_image_after_going_back` |
| G2 | 2 | local (general) | `lado:previous` is one name per machine; a second compose project overwrites it | confirmed | minor | declined: rare, the image is not published yet (T7) |
| H1 | 3 | local (spec) | the Purpose of `openspec/specs/container/spec.md` still names the old update command | confirmed | minor | fixed at archive: the Purpose names the compose file's update and the migration |
| H2 | 3 | local (tests) | a fixture of `web/src/SystemPanel.test.tsx` holds the old hint | confirmed | minor | declined: the mock only checks what it is fed |

## Checks

- On `9fb3de6`: `make lint` 0; `make test` 3196 passed; `uv run pytest -m ui
  tests/ui/test_system_panel.py` 5 passed; `openspec validate migration-backup --strict`
  valid, `--specs --strict` 26 passed; CI of PR #58 23/23 green, `container (amd64)`,
  `container (arm64)`, the smoke and `ci-ok` included.
- At archive: `openspec validate --specs --strict` 27 passed.

## Not checked (residual risk)

- `make test-integration` as a whole, `make test-container` and `make test-smoke` were
  not run locally; CI ran them, green.
- `make test-live` was not run.
- The compose header's steps are tested with the image under test in the role of the
  image before; that `docker compose pull` drops the old image on Docker's containerd
  store was checked by hand by the developer (Docker 29). No earlier image is published.

## Found on the way

- None.
