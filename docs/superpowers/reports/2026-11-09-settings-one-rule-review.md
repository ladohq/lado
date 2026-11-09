# LAD-243 settings-one-rule: review report

Pull request #261 `fix/lad-243-settings-one-rule` → `main`. Scale: tweak. Head reviewed:
`4e3ce1b5`. Settings → Statistics becomes a switch (not chosen shows as off with its line, the
banner keeps asking); removing a model on Model servers never asks, by × or by its tick, a default
too, and offers Undo where the human acted (under the tick for an untick); removing a server keeps
its question. Delta: changes to `usage-telemetry` and `model-settings-page`.

## Rounds

1. Local, precision, `origin/main...dac9f51a`, with the change's spec read whole. Found F1.
2. Local, precision, `dac9f51a..4e3ce1b5`: no new finding; F1 closed.
3. External 1, Claude Code GitHub Action: E2 and E3 minor, E1 refuted. It read the code
   (`removedModels.tsx`, `ModelSettings.tsx`, `ModelSources.tsx`, `Telemetry.tsx`, `styles.css`),
   not the tests, docs, specs or the changelog.

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Question #4907** at the design gate: a switch for every on/off setting (A); Undo wherever a
  removal can be brought back, a question only where it cannot (A); the rule holds for Settings
  only.
- **Gate `merge_ok`, approved** with no comment: E2 and E3 stay declined.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | Unticking a model its server no longer lists removed it unasked, but its row went with the open list of CLIs, the line `Removed …` and Undo; the focus fell to `body`; for a default, the model and the default were lost with no Undo | fixed in `4e3ce1b5`, test in `ModelSources.test.tsx` ("a default the list no longer has, unticked…") |
| E1 | — | external: from "not chosen", Statistics' first click can only choose `on` | refuted: the human's decision #4907, its cost written in the proposal and `ui.md` |
| E2 | minor | external: a refused tick again loses the untick's line and its Undo (`forget` before `addModel`) | declined: the refusal shows in the tick's line, the model stays removed, a tick again retries |
| E3 | minor | external: the Undo timer starts anew when the line is unmounted and mounted again (a search hid and returned the model) | declined: it only lengthens the Undo window |

## Checks

| Check | Head | Result |
|---|---|---|
| CI of the pull request, required `ci-ok` | `4e3ce1b5` | green after a rerun of `ui (1)` (run 42515114557) |
| `make lint` | `4e3ce1b5` | clean |
| `make web` (vitest, tsc, stale types, build) | `4e3ce1b5` | 1796 passed (78 files) |
| UI `test_models_section.py`, `test_statistics.py` | `4e3ce1b5` | 28 passed |
| `openspec validate settings-one-rule --strict`; `--specs --strict` and the trial archive | `4e3ce1b5`; `dac9f51a` | valid; 80 passed |
| `openspec validate --specs --strict` after the archive | archive commit | 80 passed |

`make test` was not run locally: no Python changed; CI ran the unit tests on 3.10 and 3.13. The
smoke was skipped by CI's skip list. The live tests were not run: `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change.

Flakes: Vitest `src/LoginSheet.test.tsx` ("OpenCode's sheet opens its own login window at once, with
Log out of one… when logged in", `TypeError` at `:238`) failed in `ui (1)` / `make dist` on the
first attempt and passed on the rerun; the pull request does not touch it.

## Metrics

Rounds: 2 local, 1 external, 0 stand-in. Local: 1 confirmed (important), 0 refuted. External: 2
confirmed minor, 1 refuted. Findings in code changed by the developer's cleanup: 0.

## What was not checked

- Integration, smoke and live tests were not run locally (the core and providers did not change).
- After the review, `main` got PR #259 (LAD-241, also the ticks of Model servers) and then #258 and
  #260; the pull request conflicted with it, and the code after that merge was not reviewed at
  `4e3ce1b5`.

## Found on the way

- The CI flake of `src/LoginSheet.test.tsx` (above), unrelated to the pull request; whether to file
  a task is the human's decision, asked by the supervisor.
