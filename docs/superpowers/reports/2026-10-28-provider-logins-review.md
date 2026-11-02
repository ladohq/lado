# LAD-157 provider-logins: review report

Pull request #182 `feature/lad-157-provider-logins` → `main`. Scale: full. Head reviewed
last: `917f4187` (= the remote head); base `origin/main` `1e15c3ed`. The Settings page
gains a Providers section: each agent CLI's login state (Claude Code, Codex, OpenCode,
Kilo), a login window in the UI, LADO secrets the agents get, and an agent without a login
that waits for it with the reason shown. `providers/` (base, claude, codex,
opencode_family), `runtime.py`, `agent_env.py` and `tests/real_clis.py` changed: live
tests may be wanted.

## Rounds

- **Round 1** (`1e15c3ed..cbe1d2b3`): a local pass in breadth with every lens. Two
  important findings (F1, F2), six minor.
- **Round 2** (`cbe1d2b3..a8af54aa`): a local precision pass over the fixes. F1, F2,
  F4-F8 resolved; F3 declined; nothing new.
- **Round 3**: external 1 of 2 (Claude Code GitHub Action), the whole pull request at
  `a8af54aa`. No blockers; E1a, E1c, E3 refuted against the code; E1b, E2, E5 minor;
  E4 is F3.
- **Round 4**: external 2 of 2, on the risky files round 3 did not read (`providers/`,
  `server/models.py`, `server/run.py`, `projects.py`, `doctor.py`, the Docker headers,
  `Providers.tsx`, `LoginWindow.tsx`). No blockers; R1, R2 minor, R3 unverifiable.
- **Round 5** (`a8af54aa..917f4187`, after the first archive failed strict validation):
  a precision pass over one commit that changes only the `container` and
  `provider-logins` deltas (the headers' UI login as an ADDED requirement of its own; the
  new capability's Purpose). A1 minor. No external round: the cap of 2 was used.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"nothing blocking" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | the `claude-folder-trust` delta described a path that did not exist: an agent waiting for its login got no trust at its start and its starter was not told | confirmed | important | fixed in `0259f1d8` |
| F2 | 1 | local | with the login state `unknown` the first run was not recorded and the agent stopped on the theme screen | confirmed | important | fixed in `920b2d35` |
| F3 | 1 | local, external 1 (E4) | `claude auth status` runs 2-3 times at an agent's start | confirmed | minor | declined: 0.085 s a call |
| F4 | 1 | local | a LADO secret with `\0` or over 64 KiB was saved and shown as set, but the reader dropped it | confirmed | minor | fixed in `33cc920b` |
| F5 | 1 | local | the Remove confirmation said running agents would stop answering | confirmed | minor | fixed in `9afa192a` |
| F6 | 1 | local | Log out was offered for a login by variable | confirmed | minor | fixed in `9afa192a` |
| F7 | 1 | local | the changelog said LADO logs Codex in from the page | confirmed | minor | fixed in `9afa192a` |
| F8 | 1 | local | the pull request's description named skipped smoke tests that no longer skip | confirmed | minor | fixed in the description |
| E1a | 3 | external 1 | a removed secret stays in a waiting window's environment | refuted | — | dropped: the window execs the CLI on the first poll that finds a login |
| E1b | 3 | external 1, 2 | `login_wait.py`'s docstring says "file layers", the project layer also reads plain variables | confirmed | minor | declined: a one-word fix |
| E1c | 3 | external 1 | no test re-reads the project layer | refuted | — | dropped: `tests/test_login_wait.py` has it |
| E2 | 3 | external 1 | the window prints "not logged in", then "is logged in" | confirmed | minor | declined: both lines true when printed |
| E3 | 3 | external 1 | `env.json` with keys stays when the window fails to start | refuted | — | dropped: both failure paths delete the agent's config folder |
| E5 | 3 | external 1 | two login windows opened at once | confirmed | minor | declined: the second gets a 400, the UI shows it |
| R1 | 4 | external 2 | an open window is returned whatever action was asked | confirmed | minor | declined: one window per CLI by the spec |
| R2 | 4 | external 2 | `LoginWindow.close()` hides the window when `closeLogin` fails, without an error | confirmed | minor | declined: the login button shows the open window again |
| R3 | 4 | external 2 | `onEnded` may fire twice on Close | unverifiable | — | residual risk, harmless; needs a browser run |
| A1 | 5 | local | the test of the headers' UI login checks its presence, not that it comes first | confirmed | minor | declined: the order holds in both files |

## Checks

Round 2 (`a8af54aa`): `make lint` green; `make test` 4439 passed, 2 skipped;
integration (3 files) 20 passed; `openspec validate provider-logins --strict` and
`--specs --strict` valid; CI 23 of 23 with `ci-ok`. Round 1 also ran
`tests/ui/test_providers_section.py`: 3 passed. Round 5 (`917f4187`): `openspec validate
--specs --strict` 50 passed; the archive tried on a copy outside the tree, then
`--specs --strict` 51 passed; `tests/test_docker.py` 94 passed, 1 skipped; CI 23 of 23
with `ci-ok`. At archive: `openspec validate --specs --strict` 51 passed, 0 failed.
Flakes: `smoke macos-latest codex` (the npm install of Codex; a runner that did not take
the job) passed on a rerun of the failed job.

## Not checked

The live tests (`make test-live`; Claude Code only with the human's yes). macOS: `claude
auth status` from a LADO process outside the graphical session may read the keychain as
no login, so the page and `lado doctor` may show "Not logged in" there; the waiting
window in tmux should see the login. R3 without a browser run. The full `make check` and
`make test-integration` ran in CI only.
