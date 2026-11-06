# LAD-203 ui-test-locale: review report

Pull request #222 `hotfix/lad-203-ui-test-locale` → `main`. Scale: hotfix, review depth:
targeted. Head reviewed: `75f7a0d2`. vitest runs with `LC_ALL=en_US.UTF-8` whatever the shell's
locale (`test.env` in `web/vite.config.ts`), and `web/src/testLocale.test.ts` holds the pin; the
rule is in `docs/testing.md`, and BACKLOG.md's entry goes. Tests and docs only: no API, schema,
MCP, CLI or UI change. No delta (`skip_specs`).

## Rounds

- **Round 1, local** (targeted, `c0e09153..75f7a0d2`): the diff read against the design and
  `tasks.md`. The diff touches no business logic or data, so no wide pass. Found F1 to F3.
- **Round 1, external** (Claude Code GitHub Action): no blockers, read every file of the diff,
  `Files not read` empty. It answered in 16 seconds, read only and ran no tests. Raised F4.

External rounds used: 1 of 1. The external reviewer is of the same model family, so its "nothing
found" carries little weight.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | the comment of `web/src/testLocale.test.ts` promises red without the pin "on any machine", but with `LC_ALL=en_US.UTF-8` in the shell the test stays green | declined: the guard works on CI, where neither `ci.yml` nor the Makefile sets `LC_ALL` |
| F2 | minor | the comment at `web/src/Chat.test.tsx:1779` lists the forms `2 Oct` and `2 окт.`, which no longer occur under the pin | declined: outside the diff, the test does not depend on the comment |
| F3 | minor | design D2 says the Intl check goes red when the pin stops reaching ICU; that holds only on a machine not in en-US, on CI it is green either way | declined: on CI the first test catches a removed pin, on a Russian machine this check does too |
| F4 | — | external: overriding an inherited `LC_ALL` depends on vitest applying `test.env` over the environment | refuted: with the pin under `LC_ALL=ru_RU.UTF-8`, 2 of 2 in `testLocale.test.ts`, 1241 of 1241 in `make web` |

## Checks

At `75f7a0d2`: `make lint` clean; `make web` under `LC_ALL=ru_RU.UTF-8` exit 0, 63 files, 1241 of
1241; `npx vitest run` under `LANG=ru_RU.UTF-8` alone exit 0, 1241 of 1241; `make test` exit 0,
4814 passed, 7 skipped; `openspec validate ui-test-locale --strict` valid; `openspec validate
--specs --strict` 59 of 59; `ci-ok` green, the smoke skipped as the pull request is within CI's
skip list.

The guard seen red without the pin, no file edited (vitest's API with `config: false`):

| Environment | Result |
|---|---|
| `LC_ALL=ru_RU.UTF-8` | both tests red (`ru_RU.UTF-8`, `ru-RU`) |
| `LANG=C.UTF-8` | the first test red |
| `LANG=en_US.UTF-8` | the first test red |
| `LC_ALL=en_US.UTF-8` | green (F1) |

Not run: macOS, as every run was on Linux, CI's too (on the human's machine: `cd web &&
LC_ALL=ru_RU.UTF-8 npx vitest run`); AC-2 on top of `epic/lad-154-models` was not repeated by the
reviewer, its 1449 of 1449 is the developer's figure, and the epic branch stays red under a
Russian locale until its next merge of main; `vite build`'s output was not compared again;
`pytest -m ui` locally (`tests/ui/` did not change, `ui (1)` and `ui (2)` green on CI); `make
check`, `make test-integration`, `make test-live` and `make test-smoke` (excluded by the
settings).

## Metrics

Rounds: 1 local, 1 external, 0 stand-in. Confirmed: 3 local (F1, F2, F3), 0 external. Refuted: 0
local, 1 external (F4). Findings in code changed by the developer's clean-up: 0. `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change: no
live tests needed before the merge. Found on the way: nothing.
