## 1. The warning

- [x] 1.1 `tests/test_self_update.py` (unit): `warning()` takes the new words of design.md D5;
  new tests, first red: a copy with no table of model servers lists the key's folder; a copy
  with one server of two lists only the other; no `model-servers/`, and a folder with no key,
  give no line about keys; an unreadable `model-servers/` lists that folder and the plan goes
  on. Check: AC-1, AC-2, AC-3.
- [x] 1.2 `src/lado/self_update.py`: `Restore.keys`, filled in `_way_back` and printed by
  `print_plan`, by design.md D1 to D5; `Restore`'s docstring says what `keys` is. Check: the
  tests of 1.1 green; `tests/integration/test_update_process.py` run with `-m integration`
  stays green.

## 2. Documents and the comment

- [x] 2.1 `docs/install.md`, "Going back to an older version": the list of what is lost gets
  model servers, models and default models, and the bullet says the warning names the key
  folders that stay. Check: AC-4.
- [x] 2.2 `docs/install.md`, the "What stays" paragraph of that section: going back to a
  version before 0.45.0 forgets the servers, models and defaults and leaves
  `~/.lado/model-servers/` with the keys; `rm -rf ~/.lado/model-servers` removes it; upgrading
  again brings no server back, and `lado doctor` calls the folders left over until they are
  removed; going back to a version that knows model servers, remove only the folders the
  warning listed, as the others hold the keys of servers still saved. Check: AC-4.
- [x] 2.3 `docs/install.md`, Docker's "Go back to the version before": the same in short, with
  `docker compose run --rm lado sh -c 'rm -rf ~/.lado/model-servers'`. Check: AC-4.
- [x] 2.4 `CHANGELOG.md`, `## 0.45.0 (unreleased)`: **Set models in Settings** in at most three
  lines, keeping what it promises; under `### Improved` one item in the user's words, at most
  three lines, on what going back says of model servers and their keys. Check: AC-5.
- [x] 2.5 `src/lado/providers/codex.py`: the comment over `LOSES_TOOLS` names
  `tests/live_models.py` (design.md D7). Check: AC-6.

## 3. Checks

- [x] 3.1 `make lint`, `make test`, `openspec validate rollback-names-model-servers --strict`,
  `openspec validate --specs --strict` and the trial archive of `.lado/sdlc.md` green; report
  the tests as numbers. Check: AC-7.
- [x] 3.2 `make test-live` by design.md D8 on OpenCode, Kilo, Codex and Claude Code;
  `build-report` gives per provider the CLI's version, passed, failed and skipped, repeats,
  each failure's cause, and the cost if the run shows it, else the trial report's estimate,
  said as an estimate. Check: AC-8.
- [x] 3.3 The pull request's description has the manual check from the start: branch, folder,
  commands, expected; `env | grep LADO_` and `unset`; a `LADO_HOME` and `LADO_TMUX_SOCKET` of
  its own. It names what stays: what was not checked, what was declined, what is out of
  scope. Check: AC-9.
