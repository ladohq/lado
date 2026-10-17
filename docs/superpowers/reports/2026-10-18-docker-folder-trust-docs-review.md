# LAD-87 docker-folder-trust-docs: review report

Pull request #92 `fix/lad-87-docker-folder-trust` → `main`. Scale: tweak, reviewed for
precision (only documentation and its unit tests changed). Head reviewed last: `e749c73`
(= the remote head). `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
`agent_env.py` and `tests/live/` did not change, so live tests are not needed before the
merge.

## Rounds

- **Round 1, local** (precision over the pull request, head `8a6444e`): the guide's claims
  checked against the provider's code. F1 and F2 (important). Sent back to the developer.
- **Round 2, local** (precision over the delta `8a6444e..e749c73`): F1 and F2 resolved;
  F3 (minor).
- **Round 1, external** (Claude Code GitHub Action over `aec403f..e749c73`, request
  06:49:00Z, "Claude finished" 06:49:49Z): nothing blocking; three minor remarks, one the
  same as F3, two refuted (E1, E2). It ran no tests. The external reviewer is of the same
  model family, so its "nothing blocking" weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | the guide and proposal.md said the trust question comes "in any permission mode but `bypassPermissions`"; LADO waits for it in every mode (`claude.py:256-258`, `runtime._first_hook_blocker`; the live test answers it in `bypassPermissions`) | confirmed | important | fixed in `e749c73`: "in every permission mode", also in proposal.md and tasks.md step 4 |
| F2 | 1 | local | the pull request's description lagged behind the diff: 7 manual steps without the worker step (tasks.md 4.1 has 8), F1's mistake repeated, no `docker compose exec` way in | confirmed | important | fixed: description rewritten, 8 steps matching tasks.md 4.1 |
| F3 | 2 | local (and external, remark 1) | docs/install.md:201 is one 137-character line in a paragraph wrapped at ~90 | confirmed | minor | declined: renders the same |
| E1 | ext 1 | external (remark 2) | README's `unset` names a fixed list and would miss e.g. `COMPOSE_FILE` | refuted | — | dropped: the comment says "unset each name printed", the list matches the guide's "Check the shell" by design (tasks.md 1.3: no new names) |
| E2 | ext 1 | external (remark 3) | "remembered on the home volume" holds only if `.claude.json` is on the volume | refuted | — | dropped: `CLAUDE_CONFIG_DIR=/home/lado/.claude` (`docker/Dockerfile:151`, `docker/profile.sh:7`) on the `home:/home/lado` volume (`docker/compose.yaml:106`) |
| C1 | 2 | CI | `integration (3.13, 2)`: error at teardown of `tests/integration/test_agent_liveness.py::test_an_agent_whose_cli_asks_first_waits_until_the_human_answers` ("session loops still running 1.25s after the test") | refuted (flake) | — | dropped: the diff touches only documents and a unit test; green after one `gh run rerun --failed` |

Metrics: 2 local rounds, 1 external, 0 substitutes. Local confirmed 3 (2 important, 1
minor), refuted 0; external confirmed 0 new (remark 1 = F3), refuted 2. CI flakes: 1.
Findings in code changed by the developer's cleanup: 0.

## Checks

- On `8a6444e`: `make lint` exit 0; `make test` 3411 passed (`tests/test_docker.py` 78
  passed); `openspec validate --specs --strict` 33 passed, the change valid. The delta of
  round 2 touched three lines of documentation only, so the local checks were not rerun.
- CI on `e749c73`: 23/23 green with `ci-ok` (lint, unit, integration, ui, container,
  smoke) after rerunning the flake C1.

## Residual risk (not checked)

- The manual check in the container (steps 1–8 of the pull request's description) is the
  human's.
- Smoke and live tests not run locally: CI ran the smoke; live is not needed.
