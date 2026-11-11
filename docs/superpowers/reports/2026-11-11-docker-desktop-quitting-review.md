# LAD-257 docker-desktop-quitting: review report

Pull request #282 `hotfix/lad-257-docker-desktop-quitting` → `main`. Scale: hotfix, depth
precision. Head reviewed: `12b9a087`. `docker/install.sh`'s `start_docker_desktop` asks
Docker Desktop again with `open -g -a Docker` every 10 seconds while it waits for `docker
info`, so a Docker Desktop that was still quitting at the first ask is started once it has
quit; the wait stays 120 seconds. Capability `docker-installer`: one requirement modified.

## Rounds

1. Local, precision, over the whole diff `origin/main...12b9a087`. The code matches the spec
   and the design's decisions (the first `open -a Docker` with its stop stays; the repeats
   use `-g` and `|| true`; the loop stays 60 sleeps). The test sits at the lowest layer that
   runs the shell's wait loop (unit, with fakes of `open` and `docker`) and was seen red
   before the fix. No findings.
2. External 1, Claude Code GitHub Action: no blockers; two nits E1, E2, both refuted. It did
   not read the openspec files; the local round did.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| E1 | nit | external: the comment, PR and tasks.md say the repeat runs "in the background", yet there is no `&` | refuted: "in the background" means `open -g` (do not bring the app to the front); `open` without `-W` returns at once |
| E2 | nit | external: Docker Desktop's Dock icon may bounce every 10 s while it quits | refuted as a defect: the trade-off taken in the design (decision 1, `-g`); the human sees it in the Mac check |

## Found on the way

None.

## Checks

On `12b9a087`:
- `make lint` green; `uv run pytest -n auto tests/test_install_sh.py` 88 passed; `make test`
  6116 passed, 7 skipped.
- `openspec validate docker-desktop-quitting --strict` valid; `openspec validate --specs
  --strict` 82 passed; a trial archive in a copy 82 passed.
- CI: 27/27 green, `ci-ok` pass; `mergeStateStatus` CLEAN.

## Residual risk

- The cause and the fix on a real macOS: whether `open -g -a Docker` starts Docker Desktop
  once the quitting process has gone, and how often its icon bounces. No Mac here; the
  human's check on a Mac (tasks 4.2, the scenario in docs/release.md) covers it.
- No container test: CI has no Docker Desktop.
- Integration, UI and smoke tests were not run locally; their files did not change and CI ran
  them green.
