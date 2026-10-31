# LAD-160 provider-login-layers: review report

Pull request #185 `feature/lad-160-provider-login-layers` → `main`. Scale: full, review in
breadth first. Head reviewed last: `e4d39359`. An agent's login now comes whole from one
layer (shell → `secrets/` → LADO's secrets → project; the highest layer that sets any of
the provider's login variables wins), Settings shows one row and one button per CLI, and
Claude Code's sheet asks how you pay (a token from `claude setup-token` or an API key)
and saves it as LADO's secret. `providers/` (base, claude), `runtime.py` and
`agent_env.py` changed: live tests may be wanted.

## Rounds

- **Round 1** (`3d3d1f34..ef6c6004`): a local pass in breadth with every lens. F1
  important (red CI), F2-F4 minor.
- **Round 2** (`ef6c6004..6db9dd79`): a local precision pass over the fixes; nothing new.
  External 1 of 2 (Claude Code GitHub Action): no blockers, E1 minor, E2 refuted.
- **Round 3** (`6db9dd79..72fd7a5b`, after the first archive failed strict validation:
  four requirements over 500 characters): a precision pass over the spec deltas only. G1
  minor; the archive tried on a copy, then `--specs --strict` 51 passed. External 2 of 2:
  E3, E4 minor. CI red on X1.
- **Round 4** (`72fd7a5b..e4d39359`): one test fix, X1 closed; nothing new. No external
  round: the cap of 2 was used.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"nothing blocking" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local, CI | an integration test replaced `agent_env.resolve`, which `runtime` no longer calls; CI red | confirmed | important | fixed in `2ffcaace` |
| F2 | 1 | local | Close while an OpenCode/Kilo login window is still opening leaves the window on the server | confirmed | minor | declined: the button shows the same window again; windows close with the server |
| F3 | 1 | local | no "Log out…" while the login state is unknown | confirmed | minor | declined: within the spec |
| F4 | 1 | local | `tasks.md` 2.1 named the wrong test file | confirmed | minor | fixed in `6db9dd79` |
| E1 | 2 | external 1 | Save writes the new secret before removing the others; an OSError midway leaves both | confirmed | minor | declined: needs a disk failure in a 700 folder; the 400 shows it |
| E2 | 2 | external 1 | `merge` with `login=()` merges by name | refuted | — | dropped: by design (D1) |
| G1 | 3 | local | "Settings shows the login…" defines `<where from>` only in its scenarios | confirmed | minor | declined: wording; scenarios and `docs/design/ui.md` name the words |
| E3 | 3 | external 2 | "sheet it opens" where OpenCode/Kilo open a login window | confirmed | minor | declined: wording; their sheet is the login window |
| E4 | 3 | external 2 | "One core function…" does not refer to the whole-login rule | confirmed | minor | declined: scenarios agree; a reference would pass the 500-character limit |
| X1 | 3 | CI | `tests/test_telemetry.py::test_long_outage_stays_bounded` had a fixed date and failed from 2026-10-31 on every branch | confirmed (cause outside the task) | important | fixed in `e4d39359`, the human's decision |

Found on the way (BACKLOG.md, P3): right after Save the row shows "Logged in" and "waits
for this login" together until "Check again" (as in LAD-157).

## Checks

Round 1 (`ef6c6004`): `make test` 4456 passed, 2 skipped; integration
`test_provider_logins.py` 7 passed; UI `test_providers_section.py` 4 passed; `make web`
1127 vitest. Round 2 (`6db9dd79`): `make lint` green; integration `test_agents.py` 32
passed; CI 23 of 23 with `ci-ok`. Round 4 (`e4d39359`): `tests/test_telemetry.py` 71
passed; `make lint`, `make test` 4456 passed, 2 skipped; CI run 41206269078 23 of 23 with
`ci-ok`, smoke on Linux and macOS for all four CLIs. At archive: `openspec validate
--specs --strict` 51 passed, 0 failed.

## Not checked

The live tests (`make test-live`; Claude Code only with the human's yes). That Claude Code
prefers `CLAUDE_CODE_OAUTH_TOKEN` to its own login file shows only on the live CLI (the
design's manual check). E1 was not reproduced: it needs an injected disk failure. The
full `make check` and `make test-integration` ran in CI only.
