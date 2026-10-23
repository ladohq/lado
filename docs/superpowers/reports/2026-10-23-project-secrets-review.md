# LAD-132 project-secrets: review report

Pull request #148 `feature/lad-132-project-secrets` → `main`. Scale: full, reviewed
breadth first. Head reviewed last: `f0228b2f` (= the remote head). `runtime.py` and
`agent_env.py` changed, so the human may want live tests before the release;
`hooks.py`, `mcp_server.py`, `providers/` and `tests/live/` unchanged.

## Rounds

- **Round 1** (`origin/main...35a7f36`): a local breadth pass: F1-F4.
- **Round 2** (`35a7f36..49d0445e`): a local precision pass; F1, F2, F4 closed; F5 found.
- **Round 3** (`49d0445e..f0228b2f`): a local precision pass; F5 closed (every `dir_fd`
  operation by name in `project_secrets.py` checks `_is_name` or takes a name from
  `scandir`); nothing new.
- **External 1** (Claude Code GitHub Action, comment 6359233971, the whole pull request
  `f6cb8d96..f0228b2f`): read `project_secrets.py`, `projects.*`,
  `agent_env.read_folder`, the server's routes and its 422 handler. E1-E5.
- **External 2** (comment 6359266827, no new commits; what external 1 left unread, by
  the coverage rule #949): read `runtime._base_env` and `_layer_warnings`,
  `agent_env.resolve`, `command` and `main`, doctor, both integration tests, the canary.
  E6-E11. Answered in comment 6359338181.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"nothing more" weighs less.

## Who read which area

| Area | Local rounds | External rounds |
|---|---|---|
| core/CLI (`project_secrets.py`, `projects.py`, `cli.py`) | 1-3 | 1 (`project_secrets.py` whole, `projects.*`); `cli.py` not read externally (prompt and refusal texts, no disk writes) |
| agent environment (`agent_env.py`, `runtime.py`) | 1 | 1 (`read_folder`), 2 (`_base_env`, `_layer_warnings`, `resolve`, `command`, `main`) |
| server (`app.py`, `models.py`, `launch.py`) | 1 | 1 (the secrets' routes, the 422 handler) |
| doctor | 1 | 2 |
| specs | 1, 2 | none (text) |
| docs | 1-3 (sampled and deltas) | none |
| tests and the canary | 1-3 | 2 (the canary and `test_project_secrets.py`) |

The secrets' write and remove paths and the canary were read by an external round, as
the brief required.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | a trailing line break was dropped twice: an agent got an empty secret, `x\n\n` arrived as `x` | confirmed | important | fixed in `49d0445e` (`project_secrets.stored`) |
| F2 | 1 | local | a secret file with mode 644 let the same name be set as a plain variable | confirmed | minor | fixed in `49d0445e` (`held`) |
| F3 | 1 | local | the reader follows links at `projects/` and `<id>/` (refuses only a link at `secrets/` and at files) | confirmed | minor | declined: the spec asks the refusal on links only for write and remove; only the same OS user can plant such a link |
| F4 | 1 | local | the PR description was stale | confirmed | minor | fixed in the description |
| F5 | 2 | local | `lado project unset <id> ../../x` removed a file outside `secrets/` | confirmed | important | fixed in `f0228b2f` (`_is_name` in `write`, `remove`, `held`) |
| E1 | ext 1 | external | a link or a loose file blocks both set and unset of a name | refuted: a loose file is removed; the refusal on a link is the spec's | — | dropped |
| E2 | ext 1 | external | `projects.unset` can half-run: the lado.db row gone, the file removal refused | confirmed | minor | declined: needs a hand-made secret file named as a plain variable; a second `unset` removes the rest |
| E3 | ext 1, 2 | external | `project_secrets.names` docstring says None, the function returns `[]` | confirmed | minor | declined: text only |
| E4 | ext 1 | external | `delete` order: a failing `remove_all` half-deletes the project | refuted: order by D10; a rerun finishes it | — | dropped |
| E5 | ext 1 | external | document that the reader follows links above `secrets/` | confirmed | minor | declined with F3 |
| E6 | ext 2 | external | `ps` checked by one snapshot | confirmed | minor | declined: argv holds only the launch file's path by construction |
| E7 | ext 2 | external | only `show-environment -g` checked, not the sessions' environment | confirmed | minor | declined: a test gap; only `PANE_VARS` go to tmux |
| E8 | ext 2 | external | the file search skips `fake-agents/`, links, and swallows `OSError` | confirmed | minor | declined: temp `LADO_HOME`, the fake agent's own report |
| E9 | ext 2 | external | no test that the bug report lacks a secret's *name* | confirmed | minor | declined: `doctor.report` never reads the secrets folder |
| E10 | ext 2 | external | `_layer_warnings` reads the folder a second time | confirmed | minor | declined: at worst an extra warning line |
| E11 | ext 2 | external | `env.json` stays when the window never starts | confirmed | minor | declined: accepted by the human (#1064) |

Metrics: 3 local rounds, 2 external, 0 substitutes. Local confirmed 5 (2 important: F1,
F5; 3 minor), refuted 0; external confirmed 9 (all minor), refuted 2 (E1, E4). Findings
in code changed by the developer's cleanup: 0; F5 sat in the first build's code.

## Checks

- `f0228b2f`: `make lint` green; `make test` 4110 passed, 2 skipped; `-m integration`
  on `tests/integration/test_project_secrets.py` and `test_project_secrets_canary.py`:
  6 passed; `openspec validate project-secrets --strict` and `--specs --strict` valid;
  a trial archive, then `--specs --strict` 45 passed; CI 39912812579 success, with the
  smoke on Linux and macOS.
- At archive: `openspec validate --specs --strict` 45 of 45.

## Found on the way

- Nothing outside the scope.

## Not checked

- The refusal on links is unit-tested only on Linux; on macOS the write passed the
  smoke in CI.
- No live run of an agent with a secret (a model call); `runtime.py` and `agent_env.py`
  changed, so the human may want live tests before the release.
- No external round read `cli.py` whole.
