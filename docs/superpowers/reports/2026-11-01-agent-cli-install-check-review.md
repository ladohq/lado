# LAD-158 agent-cli-install-check: review report

Pull request #188 `hotfix/lad-158-agent-cli-install-check` → `main`. Scale: hotfix,
reviewed by precision. Head reviewed last: `2b865e5c` (= the remote head). npm drops an
optional dependency that fails to install without an error, so a CLI install can exit 0
with a CLI that does not run (Codex on macOS lost `@openai/codex-darwin-arm64` in CI run
40708216095). A smoke cell now installs its CLI in up to three attempts, each checked with
`<cli> --version`, with a `::warning::` and an `npm uninstall` between them; the image's
build runs each of the four CLIs' `--version` (with a throwaway `HOME=/tmp/cli-home`)
right after its install. Nothing under `src/` changed.

## Rounds

- **Round 1** (`origin/main...2b865e5c`): a local precision pass over the whole diff and
  the spec check; external 1 of 1 (Claude Code GitHub Action, comment 6561985654: "No
  blocking findings"). The external reviewer read every risky file (`smoke_ci.py`, the
  Dockerfile, the tests), not the openspec documents, which the local pass checked.

External rounds used: 1 of 1. The external reviewer is of the same model family, so its
"no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | Task 3.2 of `tasks.md` unchecked though its checks passed | declined as bookkeeping; checked at the archive |

## Checks

- Local on `2b865e5c`: `make lint` green; `make test` 4634 passed, 7 skipped;
  `tests/test_smoke_ci.py` and `tests/test_docker.py` 161 passed, 1 skipped; `openspec
  validate agent-cli-install-check --strict` valid; `openspec validate --specs --strict`
  53 passed.
- CI on `2b865e5c`: all 23 jobs green, `ci-ok` included (container amd64 and arm64, smoke
  ×8 on Linux and macOS).

## Not verified

- The retry path never fired in real CI (no `::warning::` in the run); only the unit tests
  with the npm stub exercise it, so a real `npm uninstall -g --prefix` and reinstall after
  a live flake was not observed.
- `make docker` and the check that the image's `/home/lado` gains no new files were not
  run locally (no Docker); the image built in CI on amd64 and arm64 and the container
  tests passed. Writes by a CLI outside `HOME` (e.g. in `/tmp`) were not examined.
- The smoke was not run locally (it needs the real CLIs); CI ran all 8 cells.
- `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
  `tests/live/` did not change: no live tests needed.
