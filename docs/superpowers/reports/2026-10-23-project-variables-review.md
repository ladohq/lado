# LAD-130 project-variables: review report

Pull request #144 `feature/lad-130-project-variables` → `main`. Scale: full, reviewed
breadth first. Head reviewed last: `8ae2c75` (= the remote head). `runtime.py`,
`agent_env.py` and `providers/base.py` (the constant `CLI_VARIABLES` only) changed, so
the human may want live tests before the release; `hooks.py`, `mcp_server.py` and
`tests/live/` unchanged. Schema migration: yes.

## Rounds

- **Round 1** (`720e3fc..1d49a75`, the whole pull request): a local breadth pass (all
  lenses and the architecture against AGENTS.md) and **external 1** (Claude Code GitHub
  Action, comment 6349983800): F3-F9.
- **Round 2** (`1d49a75..8ae2c75`): a local precision pass over the delta (only
  `specs/agent-variables/spec.md`, +19 lines, and the new PR description); no new
  finding. The code had not changed since external 1, so no second external round was
  asked.

External rounds used: 1 of 2. The external reviewer is of the same model family, so its
"nothing more" weighs less.

## Who read which area

| Area | Local rounds | External rounds |
|---|---|---|
| core/CLI (`projects.py`, `state.py`, `cli.py`, `doctor.py`, `providers/base.py`) | 1 | 1 |
| agent environment (`agent_env.py`, `runtime.py`) | 1 | 1 |
| server (`app.py`, `models.py`, `launch.py`) | 1 | 1 |
| tests (unit, integration, smoke) | 1 | 1 (in part) |
| specs, docs, OpenAPI, CHANGELOG | 1, 2 | none (text, read locally) |

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | the living spec `agent-variables`, "Without an outside folder an agent's environment is as before", still named only the login shell, LADO and the provider; the delta did not modify it | confirmed | minor | fixed in `8ae2c75`: MODIFIED in the delta |
| F2 | 1 | local | the PR's manual check lacked `env \| grep LADO_` and `unset` before the start, a check after `unset`, and `unset` at the end | confirmed | important | fixed in the PR description |
| F3 | 1 | external 1 | `cli._agents_path` calls `resolve()` without the project; a comment proposed | confirmed | minor | declined: decision D4, `PATH` is reserved, behaviour right |
| F4 | 1 | external 1 | `_layer_warnings` reads the project's variables a second time after `_base_env` | confirmed | minor | declined: a window of milliseconds, only a warning's text at stake |
| F5 | 1 | external 1 | a race of `set_variable` with `projects.delete` gives `IntegrityError` (500 in the API, a traceback in the CLI) | confirmed | minor | declined: needs a concurrent `delete` and `set` by the human |
| F6 | 1 | external 1 | a lone surrogate in the API's JSON: 422 from pydantic instead of 400 from `check_variable` | confirmed (probe: `json_invalid`) | minor | declined: the value is refused and nothing stored; only the code and text differ |
| F7 | 1 | external 1 | agents of one session may hold different values until restarted; asked for a doc line | refuted: `docs/design/agents.md` says it | — | dropped |
| F8 | 1 | external 1 | the substring `KEY` gives false refusals | refuted: the human's decision (#966, D2), test `MONKEY_MODE` | — | dropped |
| F9 | 1 | external 1 | values in clear text in the API | refuted: plain variables are visible by the concept; secrets are S5b | — | dropped |

Metrics: 2 local rounds, 1 external, 0 substitutes. Local confirmed 2 (F1, F2), refuted
0; external confirmed 4 (F3-F6, all minor), refuted 3 (F7-F9). Findings in code changed
by the developer's cleanup: 0.

## Checks

- `1d49a75`: `make lint` green; `make test` 3954 passed, 2 skipped; `-m integration` on
  the 6 changed files: 51 passed (matched with `--collect-only`); `openspec validate`
  of the change and `--specs --strict` 45 of 45, a trial archive; `openapi.json` up to
  date; CI 23 of 23.
- `8ae2c75`: `openspec validate project-variables --strict` valid; a trial archive in a
  scratch copy (+17 ~7), then `openspec validate --specs --strict` 45 of 45; CI 23 of 23
  (`ui (2)` failed once on the known flake LAD-127 and passed on a rerun, by the
  developer's word).
- At archive: `openspec validate --specs --strict` 45 of 45.

## Found on the way

- Nothing outside the scope.

## Not checked

- Smoke and UI e2e tests ran only in CI; `make test-live` did not run: the live run on
  the four CLIs is planned before the release, Claude Code only with the human's yes; it
  also covers F1 of S3.
- The external reviewer read the sources; tests, docs and specs were read line by line
  only locally.
