# LAD-151 codex-sandbox-in-container: review report

Pull request #200 `hotfix/lad-151-codex-sandbox-container` → `main`. Scale: hotfix, review
depth: precision, widened to breadth in round 1 (the diff touches the sandbox of every
Codex agent). Head reviewed: `753b56d7` (= the remote head). Before each launch of a Codex
agent on Linux in any mode but `bypassPermissions`, LADO asks Codex itself whether its
sandbox starts (`codex sandbox -- true` with the agent's home); in LADO's container a
sandbox that cannot start (bubblewrap needs a user namespace, which Docker's seccomp
refuses) gives way to `--sandbox danger-full-access` with the mode's approvals kept, and
on a host the sandbox stays; both warn at the launch. `providers/codex.py` changed.

## Rounds

- **Round 1** (`origin/main...b0b4084d`): local, breadth; lenses spec, tests, silent
  failures, comments and docs, general, architecture against AGENTS.md (types skipped: no
  new types). F1 (important) and F2 (minor) → changes.
- **Round 2** (`b0b4084d..753b56d7`, four commits: `real_clis`, the smoke, modules.md,
  tasks.md): local precision, and external 1 of 1 (Claude Code GitHub Action), which read
  `codex.py`, `tests/conftest.py` and `tests/real_clis.py` but not the unit, smoke and
  container tests, the docs or openspec (the local review read those). No blocking or
  important findings.

External rounds used: 1 of 1 (the hotfix cap). The external reviewer is of the same model
family, so its "no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | The autouse fixture `codex_sandbox` replaced `codex._sandbox_error` in the smoke and live tests too, so the real probe never ran against the real Codex on any automated layer | fixed in 921cb338 + 5cf62164: `real_clis.SANDBOX_ERROR`, the smoke checks that the real probe runs and that the warning matches its answer |
| F2 | minor | A line of `docs/design/modules.md` longer than the wrap width | fixed in 5cf62164 + 57b2814f |
| F3 | — | What the real probe answered on ubuntu-latest is not recorded; the smoke is right for either answer | unverifiable: carried as a risk |
| F4 | minor | A short line left in a paragraph of `docs/design/modules.md` | declined at convergence: cosmetic |
| F5 | minor | The pull request's description says both that the Codex smoke ran and that it did not | declined at convergence: the diff is described right |
| E1 | minor | external: the probe runs `"codex"`, the launch `self.command` | declined: the same binary today |
| E2 | — | external: a timeout counts as "cannot start" and drops the sandbox in the container | refuted: decision D1, with a warning at every launch |
| E3 | — | external: `subprocess.run` with a timeout may hang on a grandchild holding the pipe | refuted: on POSIX it kills and waits after the timeout |
| E4 | — | external: the probe runs at every launch | refuted: decision D6 |
| E5 | — | external: config.toml is written twice | refuted: the first write is the probe's |
| E6 | minor | external: the warning's cause is built when there is no error | declined: readability only |
| E7 | — | external: read-only roles lose Codex's write limits in the container | refuted: read-only roles do not rely on Codex's sandbox (`docs/design/agents.md`) |

## Checks

- Round 1 on `b0b4084d`: `make lint` green; `make test` 4725 passed, 7 skipped;
  `openspec validate codex-sandbox-in-container --strict` valid; `openspec validate
  --specs --strict` 54 passed.
- Round 2 changed only tests, docs and openspec; CI on `753b56d7` 23/23 with `ci-ok`, the
  container cells on amd64 and arm64, and the Codex smoke on Linux and macOS 8 passed
  each, with the real probe.

## Residual risk

- F3: that the real probe exits 0 on a Linux host whose sandbox works, so no false
  warning there, is not shown.
- Task 4.2, the scenario "A shell command in the container": a shell command runs with no
  "retry without sandbox?" question; the human's manual check on the next release
  candidate.
- `make test-container` was not run locally (no Docker); CI ran it.
- The live tests were not run; they run at a release, and since F1 they use the real
  probe.
