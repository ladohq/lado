# LAD-63 ui-server-in-container: review report

Pull request #45 `feature/lad-63-container-links` → `main`. Scale: full, breadth first,
then precision. Head reviewed last: `659d6bf` (= the remote head); the archive commit
follows it. `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` did not change, so live tests are not needed before the merge.

## Rounds

- **Round 1, local** (breadth over `origin/main...85a2c3a`; lenses spec, tests, silent
  failures, comments, types, general, architecture against AGENTS.md): F1 important, F2-F4
  minor, all sent to fix.
- **Round 2, local** (precision over the fix commit `85a2c3a..659d6bf`): no new finding.
  Checked that the fixes did not break their neighbours: `checking` also goes through
  `toCheck`, so the spinner does not hang; `problem` is empty for a value not checked;
  `sameFolder` holds for `repos="/"`; the spec, AGENTS.md and ui.md match the code.
- **Round 1, external** (Claude Code GitHub Action, request 2026-10-14T19:38:23Z, answer
  19:39:31Z, on `659d6bf`): no blocker, F1-F4 confirmed closed; E1 declined, E2 dropped,
  a third remark no finding. The analysis is posted on the pull request.

External rounds used: 1 of 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (reading and a Chromium probe) | the `Repositories folder` chip opened the list of subfolders but left the focus on the button: the list stayed over the form, a click aside did not close it, arrows, Enter and Escape did nothing | confirmed | important | fixed in `659d6bf` (`input.current?.focus()`), vitest "the Repositories folder row puts the folder in Where and lists it"; probed again in Chromium |
| F2 | 1 | local | `doctor.check_repos_folder`: `Path.exists()` raised `PermissionError` for a `LADO_REPOS` under a folder LADO may not read | confirmed | minor | fixed in `659d6bf` (one `stat`: missing is INFO, another `OSError` a WARN with the reason), `tests/test_doctor.py::test_a_repositories_folder_lado_may_not_look_at_warns_with_the_reason` |
| F3 | 1 | local | stale docstring of `/api/clone-target` ("by default ~/lado/<repo>") | confirmed | minor | fixed in `659d6bf`, `web/openapi.json` and `web/src/api.gen.ts` made again |
| F4 | 1 | local (Chromium probe) | after the chip, Where held the repositories folder itself, and the folder check offered `git init && git add -A && git commit` for it | confirmed | minor | fixed in `659d6bf`: `toCheck` skips `sameFolder(path, repos)`, with and without a trailing slash; vitest "the repositories folder itself in Where is not checked…" |
| E1 | ext 1 | external | in a container with the server on loopback, `lado ui` prints the container's 127.0.0.1 link and "Open it in your browser on the host.", which the host cannot open | confirmed | minor | declined: the proposal puts a loopback server inside the container out of scope; it is the image's command line (T3 runs the server on `0.0.0.0`); the human decides at the merge |
| E2 | ext 1 | external | a host port other than the container's makes the link wrong | refuted as a defect of the change | — | dropped: out of scope in the proposal and in the pull request's "Deliberately not done" |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 4 (F1-F4) | 0 | 0 |
| external, Claude Code Action | 1 (E1) | 1 (E2) | 0 |

## Checks

- Reviewer on `659d6bf`: `make lint` clean; `make test` 3011 passed;
  `uv run pytest -m integration -n auto tests/integration/test_server_process.py` 8
  passed; `uv run pytest -m ui tests/ui/test_launch.py` 15 passed; `make web` 718 vitest
  passed, types fresh; `openspec validate ui-server-in-container --strict` valid;
  `openspec validate --specs --strict` 20 passed.
- CI on `659d6bf` green, 21/21: unit 3.10 and 3.13, integration × 6, js, ui × 2, smoke on
  Linux and macOS for all four providers, ci-ok.

## Found on the way

None.

## Not checked

- The check by hand in Docker (the LAD-52 prototype) is known from the developer's report
  only; the T3 image and compose do not exist yet.
- A host port other than the container's gives a wrong link: so decided in the design.
- `make check` and `make test-integration` not run locally as a whole; the green CI covers
  them. Live tests not run (no provider changed).
- The external reviewer is the same model family.

## Result

Converged after round 2 (1 of 2 external rounds).
