# LAD-299 github-com-entry: review report

Pull request #339 `feature/lad-299-github-com-entry` → `main`. Scale: full. Head
reviewed: `3a40dc29`. The GitHub login of before (`GH_TOKEN`, `gh auth login`) is taken
over once into a saved github.com entry; from then on github.com is an ordinary saved git
server of Settings → Git servers, `gh` gets its token (and a GitHub Enterprise entry's
host) from the entry, and an outside `GH_TOKEN`, `GITHUB_TOKEN` or `gh` login, or a
project's `GH_TOKEN` secret, is named loudly as set but not used.

## Rounds

1. Local, a full pass over `origin/main...c5344c82`: spec, tests, silent failures,
   comments and docs, types, general, and the architecture against AGENTS.md. Found
   F1–F8 (one blocker, three important); F3 went to the human.
2. Local, precision on the delta `c5344c82..3a40dc29` (the fixes of F1, F2, F4, F6).
   External 1, Claude Code GitHub Action: E1–E5, no blocker or important. It read
   `github_takeover.py` and the diffs of `git_servers.py`, `agent_env.py`, `runtime.py`,
   `state.py`, `server/run.py`; it did not read `docker/*`, `server/git_entries.py`,
   `cli.py`, `clone.py`, `doctor.py`, `gitcache.py`, the tests, docs, openspec or web.

External rounds used: 1 of 2. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | blocker | processes opening a new lado.db at once raced creating its schema (`SchemaError … version 0`, `duplicate column name`; 159 red CI tests) | fixed in `3a40dc29`: the schema is made under a lock on `LADO_HOME`; the test was seen red on the old `state.py` |
| F2 | important | `.local/state/gh/device-id` committed by accident | fixed in `3a40dc29` |
| F3 | important | the taken-over github.com entry sends `git@github.com:` addresses over https with the entry's token, whose rights may differ from the ssh key's | accepted by the human: the user can replace the token |
| F4 | important | `docs/marketplaces.md` and `gitcache.py`'s docstring offered `GH_TOKEN` | fixed in `3a40dc29` |
| F5 | minor | a pending takeover is retried at each agent start (`gh auth token`, up to 10 s) | declined: rare; doctor says pending |
| F6 | minor | design D10 promised both hint commands in the UI | fixed in `3a40dc29` |
| F7 (+E1) | minor | takeover errors other than a refusal stop `lado start`/`lado ui` and an agent's start | declined: loud; the start touches lado.db and would fail anyway |
| F8 | minor | `docs/install.md` does not say that ssh addresses of a saved server go over its token | declined: described in `docs/cli.md`; came after the developer's report |
| E2 | minor | `GITHUB_TOKEN` is removed from every agent, also for OpenCode/Kilo's GitHub Models | declined: design D4; doctor names it as not used |
| E3 | — | `flock` may not hold on NFS | unverifiable here; residual risk |
| E4 | minor | the 10 s WAL retry beside `timeout=10` wants one constant | declined: style |
| E5 | — | `SCHEMA` is not idempotent on a retry after a crash | refuted as a defect of this work: under the lock a second process waits for the first |

## Metrics

- Rounds: 2 local, 1 external, 0 stand-ins.
- Confirmed: local 8 (F1–F8), external 4 (E1–E4; E1 merged into F7, E3 unverifiable).
- Refuted: local 0, external 1 (E5).
- Findings in code changed by fixes: 0.

## Checks

- Round 1: `make lint` clean; `make test` 5863 passed, 15 skipped; integration on the
  three changed files 22 passed; `openspec validate --specs --strict` and the trial
  archive 87/87.
- Round 2: `make lint` clean; the race test 1 passed at `3a40dc29`, 1 failed on the old
  `state.py`. The developer's runs: 5864 unit, 629 ui, 314 integration passed.
- CI at `3a40dc29`: 27/27 successful (`ui (3)` once red on the known flake
  `tests/ui/test_launch.py::test_on_a_phone_every_field_and_button_of_the_window_is_a_44_px_target`, LAD-298, passed on a rerun).
- Not run: container and smoke locally (green in CI), `make test-live`.

## Found on the way

- A process that dies in the middle of a new lado.db's schema leaves it at `user_version`
  0 with part of the tables, and every later start fails with `SchemaError`; as before
  this pull request.
- `unit (3.14)` once red on
  `tests/test_model_servers.py::test_a_late_control_is_asked_again_and_still_proves_nothing`
  (`assert 1 == 2`) at an earlier head; green at `3a40dc29`.

## Residual risk

- `flock` on NFS and other unusual volumes (E3).
- The hint for a server kind without a token on a real GitHub Enterprise, `gh` on a GHE
  with a port or path, and a real `gh pr create`: left to the human's manual check.
- OpenCode/Kilo's GitHub Models through `GITHUB_TOKEN` (E2) not checked live.
- The pull request changes `runtime.py` and `agent_env.py`; `make test-live` not run.
