# LAD-161 refuse-start-without-login: review report

Pull request #184 `feature/lad-161-refuse-start-without-login` → `main`. Scale: full.
Head reviewed last: `172ec763` (= the remote head), with `origin/main` `16d69431` (LAD-160,
provider-login-layers) merged in. A new session or worker whose CLI needs a login (Claude
Code) and has none is refused before it starts; the New session window and the providers
list say which CLI lacks its login; LAD-157's login wait stays as the fallback for a
resume or a login lost after the check. The check reads the login in the environment the
agent gets (`agents_env(agent_layers(project), cli)`), so LAD-160's "the method chosen on
the page wins" holds. `runtime.py` changed: live tests may be wanted.

## Rounds

- **Round 1** (`origin/main..b7e5cd30`): a local pass in breadth with every lens and the
  spec check; external 1 of 2 (Claude Code GitHub Action). F1 important, L1 minor, E1-E5
  refuted.
- **Round 2** (`b7e5cd30..e8588995`): a local precision pass over the F1 fix; external 2
  of 2: no findings.
- **Round 3** (`e8588995..38fb48fb`), after the first archive failed strict validation (a
  modified requirement over 500 characters): the requirement's text shortened, its meaning
  kept. X1 (a date-bound test red in CI, outside the PR) and X2 (13 files conflicting with
  `origin/main` after LAD-160) found.
- **Round 4** (`38fb48fb..172ec763`): a local precision pass over the merge of
  `origin/main` and one fix. The login check, the providers list and the start pre-check
  build the agent's environment the way its launch does; the modified requirement keeps
  LAD-160's wording and all five scenarios. No new findings; no external round: the cap of
  2 was used.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"no findings" weighs less, and it did not see the merge with LAD-160.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | Two new `login_missing` tests passed only with `claude` on PATH; CI `unit (3.13)` red | fixed in `e8588995` (fixture `clis_run`) |
| L1 | minor | In the Project method the Provider field flashes "checking…" while the project loads | declined: cosmetic, Start is disabled meanwhile |
| X1 | outside the PR | `tests/test_telemetry.py::test_long_outage_stays_bounded` pinned to a date beyond the 30-day report window | fixed in main (LAD-160, `e4d39359`) by the human's decision, merged in `460ab7f1` |
| X2 | blocker | Merging `origin/main` (LAD-160) conflicted in 13 files | resolved in `460ab7f1` and `172ec763`, checked in round 4 |
| E1-E5 | — | external: worktree restore on a refused worker, no pre-check for an unknown provider, cost of `GET /api/providers`, missing hint, direct `database()` call | refuted against the code (D2, docs/cli.md, `Launch.tsx`, `app.py`) |

## Checks

- Local on `172ec763`: `make lint` green; `make test` 4474 passed, 2 skipped; integration
  `tests/integration/test_provider_logins.py` 9 passed; `openspec validate
  refuse-start-without-login --strict` valid; a trial archive then `openspec validate
  --specs --strict` 51 passed.
- CI on `172ec763`: all 23 jobs green, `ci-ok` included (unit, integration ×6, ui ×2,
  container ×2, smoke ×8 on Linux and macOS).

## Not verified

- Live tests (`make test-live`) were not run; `runtime.py` (`check_login`,
  `check_start_login`, the public `agent_layers` and `agents_env`) changed.
- The merge with LAD-160 was reviewed only locally.
- `make check` as a whole was not run locally; CI ran it in full.
