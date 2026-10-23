# LAD-137 new-session-in-project: review report

Pull request #155 `feature/lad-137-new-session-in-project` → `main`. Scale: full change.
Head reviewed last: `e53f103f` (= the remote head). The New session window's Project way
(`web/src/Launch.tsx`, `web/src/LaunchProject.tsx`), the server's start with a project
(`server/app.py`, `server/launch.py`, `server/models.py`), `projects.py` and
`runtime.py` changed. `runtime.py` changed only by moving `project_session_name` out,
with the same behaviour; `providers/`, `hooks.py`, `mcp_server.py` and `agent_env.py`
did not change. Live tests were not run.

## Rounds

- **Round 1, local, broad** (`origin/main...075eabf7`): lenses spec, tests, silent
  failures, comments, types, general, and the architecture against AGENTS.md. Found F1
  and F2.
- **Round 2, local, precise** (`075eabf7..fad69c37`): no new findings.
  - External 1 (Claude Code Action, `main...fad69c37`): E1-E4; the risky files were read
    only in part.
  - External 2, for the coverage of the risky code alone: every risky file read whole;
    found X1-X4.
- **Round 3, local, precise** (`fad69c37..e53f103f`): found Y1.
  - External 3, past the cap of 2 with the human's yes (#1332, #1334), on the same
    delta: Z1-Z3, no blocker or important.

External rounds used: 3 (cap 2, plus 1 by the human's decision).

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | after a 409 in Project, "Resume it" and "Open it" vanished when the workspace path goes through a symlink: the window compared git's root with an unresolved path | confirmed | important | fixed in `fad69c37` (`ProjectLaunch.root`), unit and vitest tests |
| F2 | 1 | local | a spec scenario said "Start session" instead of "Start in <title>" | confirmed | minor | fixed in `fad69c37` |
| E1 | 2 | external 1 | a requested project or repository that does not exist is silently replaced by another | confirmed | minor | declined: the window shows what is chosen and the button names the project |
| E2 | 2 | external 1 | when git does not answer, `root` falls back to the unresolved path | confirmed | minor | declined: such a folder is no repository, and the start refuses it in `check_repo` |
| E3 | 2 | external 1 | `_project_place` crashes in a race with a project's removal | refuted: `/api/folders` is wrapped in `core()`, the answer is a 400 | — | dropped |
| E4 | 2 | external 1 | the list lacks Home and End | refuted: the ARIA radio group pattern does not require them | — | dropped |
| X1 | 2 | external 2 | while a request runs, the Where block unmounts: the list vanishes, focus is lost, the arrows stop working | confirmed | important | fixed in `e53f103f` (the last answer stays, `aria-busy`), vitest seen red first |
| X2 | 2 | external 2 | after a 409 in Project, "Resume it" and "Open it" were offered for a session of another project | confirmed | minor | fixed in `e53f103f` by the human's decision #1332 (`SessionInfo.project` compared), two vitest tests |
| X3 | 2 | external 2 | a name typed in another way carries over into Project | confirmed | minor | declined: one `name` state for all ways, as before; the button names the project |
| X4 | 2 | external 2 | `projects.place` runs git on every check | refuted: only for a refused folder in `projects/`, debounced | — | dropped |
| Y1 | 3 | local | while another project is asked, the field briefly shows the new id with the old repositories, name and hint | confirmed | minor | declined: the start is off until the current answer arrives |
| Z1 | 3 | external 3 | `aria-busy` stays on the list after a failed request | confirmed | minor | declined: polish |
| Z2 | 3 | external 3 | the `setLastProject` effect costs an extra render per answer | refuted: harmless | — | dropped |
| Z3 | 3 | external 3 | while a request runs, kits are asked for `""` instead of the repository | confirmed | minor | declined: as before this change, brief, the start is off |

Metrics: 3 local rounds (1 broad, 2 precise), 3 external, 0 substitutes. Local confirmed
3 (F1, F2, Y1), refuted 0; external confirmed 7 (E1, E2, X1, X2, X3, Z1, Z3), refuted 4
(E3, E4, X4, Z2). Findings in code changed by the developer's cleanup: not tracked, none
known.

## Gate #107

All three conditions met: the button reads "Start in <title>"; a UI e2e test chooses a
project that was not preselected; a test covers the longest project id and repository
name. The start goes through the CLI's `runtime.start_session`, with no second
implementation, as all three external rounds confirmed.

## Coverage of the risky code (#949)

| File | Local | External 1 | External 2 | External 3 (delta) |
|---|---|---|---|---|
| `server/app.py` | changed parts whole | partly | whole | unchanged |
| `server/launch.py` | whole | partly | whole | unchanged; `ProjectLaunch` contract checked |
| `server/models.py` | changed parts | diff | whole | contract by grep |
| `projects.py` | changed and related | partly | whole | unchanged |
| `runtime.py` | changed and `start_session` | partly | lines 1-1000 (all project code) | unchanged |
| `web/src/LaunchProject.tsx` | whole (rounds 1, 3) | whole | whole | whole |
| `web/src/Launch.tsx` | diff and related (rounds 1, 3) | diff | whole | every part of the Project way |

## Checks

- On `e53f103f`: `openspec validate new-session-in-project --strict` valid;
  `openspec validate --specs --strict` 46 passed; vitest `Launch.test.tsx` and
  `LaunchProject.test.tsx` 154 passed; CI 23/23, `ci-ok` green.
- On `fad69c37`: `make lint` exit 0; unit `test_server_project_launch.py` and
  `test_server_launch.py` 105 passed.
- On `075eabf7`: the canary 2 passed; unit tests of the touched files 237 passed.

## Not checked

- Not run locally: the whole `make test`, UI e2e, `make web`, the whole
  `make test-integration`; CI ran them, and the smoke.
- `make test-live` not run (only at a release, with the human's yes), though
  `runtime.py` changed.
- `runtime.py` past line 1000 was not read externally; it holds no project code.
- The `NameHint` texts in Project ("another folder", "this folder") are imprecise in one
  edge case: a session of the same folder started before the project existed.

Found on the way: nothing.
