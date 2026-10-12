# LAD-6 clone-from-url: review report

Pull request #6 `feature/lad-6-clone-from-url` → `main`. Scale: full.
Head reviewed last: `2c76eb0`; the archive commit follows it. The human's decision on F4:
`clone.ABANDONED` is 150 s, and a window that goes away cancels its clone at once by a
beacon on `pagehide`.

## Rounds

- **Round 1** (`origin/main..06a0461`): local breadth review (spec, tests, silent failures,
  comments, types, general, architecture against AGENTS.md; the UI lens by a helper, its
  findings checked against the code). 5 important, 7 minor.
- **Round 2** (`06a0461..dc47c55`): precision; F1–F12 closed, F14 declined.
- **Round 3** (`main...dc47c55`): external 1 of 2, Claude Code Action
  (https://github.com/ladohq/lado/pull/6#issuecomment-6122606264). 3 important, 3 minor,
  1 refuted.
- **Round 4** (`dc47c55..0555632`): local precision and external 2 of 2
  (https://github.com/ladohq/lado/pull/6#issuecomment-6122792659). Only 2 minor, both
  declined.
- **Round 5** (`0555632..2c76eb0`, spec only): after the first archive failed (`openspec
  archive` wrote a placeholder `## Purpose` into the new capability `session-clone`, which
  `openspec validate --specs --strict` refuses), the delta got its Purpose. The archive
  and the strict validation were reproduced on a throwaway copy. No external round: the
  cap was spent and the delta has no code.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local: spec | The CLI did not print a `CloneError`'s hint | confirmed | important | fixed in `c9318a8` |
| F2 | 1 | local: silent failures | A `PermissionError` on checking or making the folder was a 500 in the API and a traceback in the CLI | confirmed | important | fixed in `c9318a8` (`no_access`) |
| F3 | 1 | local + UI helper | One failed poll dropped the window while the clone went on, with no Cancel clone | confirmed | important | fixed in `c9318a8` |
| F4 | 1 | local: general | A background tab polls once a minute; `ABANDONED` of 10 s cancelled a live clone | confirmed | important | fixed in `dc47c55` (human's decision: 150 s and a beacon) |
| F5 | 1 | UI helper | Enter in the long branch field cloned the default branch | confirmed | important | fixed in `c9318a8` |
| F6 | 1 | UI helper | Under StrictMode `alive.current` did not return to `true` | confirmed | minor | fixed in `c9318a8` |
| F7 | 1 | UI helper | URL mode took kits and mode from the folder shown before | confirmed | minor | fixed in `c9318a8` |
| F8 | 1 | local: general | A URL with no repository name gave the folder `~/lado` | confirmed | minor | fixed in `c9318a8` and `0555632` |
| F9 | 1 | local: spec | `tasks.md` 6.1 not checked | confirmed | minor | fixed in `dc47c55` |
| F10 | 1 | UI helper | "Resume it" not disabled while busy | confirmed | minor | fixed in `c9318a8` |
| F11 | 1 | UI helper | A late Cancel clone still started the session | confirmed | minor | fixed in `c9318a8` |
| F12 | 1 | UI helper | "—" instead of `fetching branches…` during the debounce | confirmed | minor | fixed in `c9318a8` |
| F13 | 1 | local: tests | No vitest of a 400/409 from `POST /api/clones` | confirmed | minor | declined: covered by `tests/test_server_clones.py` |
| F14 | 2 | local: precision | A poll that keeps failing (server down) keeps the window locked | confirmed | minor | declined: a reload frees it, the beacon cancels the clone |
| F15 | 3 | external (Action) | git ran an askpass helper despite "never a wait" | confirmed | important | fixed in `0555632` (`GIT_ASKPASS` empty) |
| F16 | 3 | external (Action) | A `.` or `..` segment gave `~/lado/..` or `~/lado` | confirmed | minor | fixed in `0555632` |
| F17 | 3 | external (Action) | SIGHUP or SIGTERM during a CLI clone left git and the temporary folder | confirmed | important | fixed in `0555632` |
| F18 | 3 | external (Action) | A job dropped after `KEPT` while the window was silent was a refusal with the clone done | confirmed | important | fixed in `0555632` (a 404 checks the folder again) |
| F19 | 3 | external (Action) | `_stop`'s last `killpg` after the leader was reaped | confirmed | minor | declined: microseconds; the pgid stays taken while members live |
| F20 | 3 | external (Action) | Unmounting the window inside the SPA leaves the clone for up to 150 s | confirmed | minor | declined: the modal makes the rest inert; the sweeper cancels it |
| F21 | 3 | external (Action) | The server can be made to reach any host | refuted | — | by design, under `Guard.changes` |
| F22 | 4 | external (Action) | After SIGHUP the unguarded `finally: shown.done()` may raise `OSError` (EIO): a traceback instead of 128+n | confirmed | minor | declined: the clone is cleaned up already |
| F23 | 4 | external (Action) | A second signal during the cleanup may cut it short and leave the temporary folder | confirmed | minor | declined: needs two signals at that moment; the hidden folder is harmless |

| Source | Confirmed | Refuted |
|---|---|---|
| local (UI helper included) | 14 (F1–F14) | 0 |
| external, Claude Code Action | 8 (F15–F20, F22, F23) | 1 (F21) |

Every important finding is fixed, each behaviour fix with a test.

## Checks

- On `0555632`: `make lint` clean, `make test` 2458 passed, `make web` 640 vitest passed
  with fresh types, UI e2e `tests/ui/test_launch.py` 12 passed, integration
  (`test_clone_start.py`, `test_server_launch_process.py`) 5 passed; CI green.
- On `2c76eb0` (spec only): `openspec validate clone-from-url --strict` valid. CI: the first
  run's `check (3.10)` failed on the unrelated
  `test_agent_liveness::test_finishing_a_worker_tells_no_one_it_stopped` (a hook wait timed
  out, the known timeout flakes of BACKLOG.md); it passed alone locally and on 3.13, and
  the rerun of the failed job was green.
- At archive: `openspec validate --specs --strict` 4 passed, 0 failed.

## Residual risk

- Live tests were not run, though `runtime.py` changed (`full_path`, `check_name`,
  `_elsewhere`); providers, hooks, MCP, `agent_env.py` and `tests/live/` did not. The
  smoke passed in CI on Linux and macOS.
- F4: Chrome's throttling of a background tab was not reproduced in a browser; the
  beacon's cancel is covered by a UI e2e test with a page reload.
- F17: covered by an integration test with a slow fake git; a real terminal closed during
  a clone was not tried.
