# LAD-59 update-in-container: review report

Pull request #40 `fix/lad-59-update-in-container` → `main`. Scale: tweak, precision
review. Head reviewed last: `2f4c0c6` (= the remote head); the archive commit follows it.
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
did not change, so live tests are not needed before the merge.

## Rounds

- **Round 1, local** (precision pass over the whole diff `c49de88..2f4c0c6`): every
  requirement and scenario of `specs/container/spec.md` has code and a test (the CLI
  refusal for `--yes`, a version and `--id`; the refusal order AGENT → CONTAINER →
  RUNNING / NO_INSTALLER; nothing stopped or written; the API's GET and the 409 of POST
  before PyPI; doctor, `lado ls` and the report; the panel by vitest and UI e2e).
  D1-D5 kept, nothing beyond the scope; the architecture against AGENTS.md: one source
  (`update.in_container`, `CONTAINER_UPDATE`), neutral core, no silent drop, the new
  `UpdateInfo.container` used by the panel. The screenshot matches option A of the mockup
  and docs/design/ui.md. F1 minor.
- **Round 1, external** (Claude Code GitHub Action, request 18:03:48 UTC, answer
  18:04:46 UTC): no blocker; E1 refuted, E2 minor.

External rounds used: 1 of 1 (the cap for a tweak).

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | `tasks.md` 4.2 is checked as first worded (the prototype's image with this branch's LADO, the panel's pill by hand), while the check by hand ran in a light variant of the prototype (no agent CLIs, a stub installer) and the panel was not looked at by hand (UI e2e checks it) | confirmed | minor | declined: the difference is described in the pull request (How it was checked) and the build report; no effect on behaviour |
| E1 | 1 | external | the refusal's text is built in two places (`self_update.refusal` and the CLI's suffix); a test should pin the CLI's exact line | refuted | — | the test exists: `tests/test_self_update.py` compares `CONTAINER_LINE` with the whole stderr for `--yes`, a version and `--id` |
| E2 | 1 | external | a long `title` string on the pill in `SystemPanel.tsx` | confirmed | minor | declined: style only, the same form as the `pre-release` pill beside it |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 1 (F1) | 0 | 0 |
| external, Claude Code Action | 1 (E2) | 1 (E1) | 0 |

## Checks

- Reviewer on `2f4c0c6`: `make lint` clean; `make test` 2987 passed;
  `uv run pytest -m ui tests/ui/test_system_panel.py` 5 passed; vitest
  `src/SystemPanel.test.tsx` 20 passed, `tsc --noEmit` clean;
  `openspec validate update-in-container --strict` valid; `openspec validate --specs
  --strict` 19 passed.
- CI on `2f4c0c6` green: check (3.10, 3.13), ui, js, smoke × 8 (Linux, macOS).

## Found on the way

None.

## Not checked

- `make check` and `make test-integration` not run locally; the green CI covers them.
  Live tests not run (no provider changed).
- `make web` as a whole (the stale-types check) not run locally; `web/openapi.json` and
  `api.gen.ts` are updated in the pull request and CI is green.
- The full LAD-52 prototype image with the agent CLIs was not built; the developer's
  check by hand ran in a light variant (the refusal, `RestartCount=0`; with
  `LADO_CONTAINER=0` it reproduced H7). To repeat on the real image in T3.
- Agents in the container get their environment from the login shell and will likely not
  see `LADO_CONTAINER` from the image's `ENV`: a `lado doctor` an agent runs would not
  say "in a container". No effect on the update (an agent's `lado update` is refused
  anyway); it belongs with the image (T3/T10).
- The external reviewer is the same model family.

## Result

Converged after round 1 (1 of 1 external rounds).
