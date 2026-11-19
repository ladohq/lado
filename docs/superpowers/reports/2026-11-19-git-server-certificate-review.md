# LAD-301 git-server-certificate: review report

Pull request #341 `feature/lad-301-git-server-certificate` → `main`. Scale: full. Head
reviewed: `6075969e`. A git server whose certificate is not trusted makes Check and Add
ask "Trust this server?" with the root the chain leads to (signed by, valid, SHA-256);
trusting saves it as the server's `ca.pem` beside its token, and LADO's git, the agents'
git (`http.<address>/.sslCAInfo` through `GIT_CONFIG_*`) and LADO's API requests to that
server trust it for that server alone. The CLI sets, shows and clears it; the clone hint
and doctor name it; doctor and an agent's start say that `gh` does not get it.

## Rounds

1. Local, a full pass over `origin/main...4205cd0b`: spec, tests, silent failures,
   comments and texts, general, and the architecture against AGENTS.md, with helpers
   for the UI and for CLI/clone/doctor/runtime (every helper finding checked). Found
   F1–F12.
2. Local, precision on `4205cd0b..90459655`. External 1, Claude Code GitHub Action
   (comment 7015850144): F9 again, F15, F16, F17. CI: F13, F14, F18.
3. Local, precision on `90459655..3da05e7d`. External 2 (comment 7016268032): no
   defects; F19, F20 as style.
4. Local, precision on `3da05e7d..6075969e` (the fix of F13); no external round, by the
   human's decision. Nothing new.

External rounds used: 2 of 2. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | blocker | the root walk looped forever on authorities signing each other | fixed in `0583bb68`, test `test_cross_signed_authorities_end_the_walk` |
| F2 | important | `min([])` crashed when an authority fetched by an issuer link had expired | fixed in `0583bb68` |
| F3 | important | a leaf not signed by itself was called "signed by itself" | fixed in `0583bb68` and `3da05e7d` |
| F4 | important | Undo of an expired certificate was refused | fixed in `90459655` |
| F5 | minor | after a PUT a refused check shows as failure though the certificate was saved | declined: needs a certificate with a lost token file |
| F6 | minor | Undo did nothing when DELETE returned `pem: null` | fixed in `90459655` |
| F7 | minor | `add --certificate -` ate the token's stdin | fixed in `90459655`: exit code 2 |
| F8 | minor | install.md promised DER `.crt` | fixed in `90459655` |
| F9 | minor | an unreadable or damaged `ca.pem` breaks Check (500) and git; the UI cannot remove it | declined: LADO writes it atomically; `lado git-server certificate <address> --clear` removes it |
| F10 | minor | the "None" line shows only until the next action | declined: the spec does not ask for it |
| F11 | minor | Add stays silent when the check after Trust offers again | declined: a race only |
| F12 | minor | Check is not disabled while Trust's PUT runs | declined: a double request, nothing wrong saved |
| F13 | important | a clone refused by curl 8 with GnuTLS was not recognised as an untrusted certificate | fixed in `6075969e`, test with the runner's real line |
| F14 | important | a unit test depended on the order of `iterdir()` | fixed in `3da05e7d` |
| F15 | minor | the CA Issuers link is fetched before the human's yes, internal addresses too | declined: design D5 (no token, `User-Agent` only, no redirects, 64 KB, 5 s) |
| F16 | — | two handshakes, PUT takes any valid PEM, a private method, Apple git | refuted: exactly the shown PEM is saved and checked again |
| F17 | minor | the renewal warning was lost for a leaf with no authority found above it | fixed in `3da05e7d` |
| F18 | — | smoke macos codex: Codex's model label | unverifiable, no cause in the diff; flake filed as LAD-302 |
| F19 | minor | three dependent flags `own`/`intermediate`/`leaf` instead of one enum | declined: consistent in every layer; a separate cleanup |
| F20 | minor | the pattern `does not match target host name` is broad | declined: applies to a failed clone's stderr only |

## Metrics

- Rounds: 4 local, 2 external, 0 stand-ins.
- Confirmed: local 12 (F1–F12), CI 2 (F13, F14), external 5 (F15, F17, F19, F20, F9
  again).
- Refuted: local 0, external 1 (F16).
- Findings in code changed by the developer's cleanup: not tracked apart; F1 and F2 lie
  in code the cleanup did not change in substance.

## Checks

- Round 4: `tests/test_clone.py` 138 passed.
- CI run 44577664919 at `6075969e`: 27/27 successful; the pull request MERGEABLE, CLEAN.
- Not run: smoke and container locally (green in CI), `make test-live`.

## Found on the way

- The smoke flake of Codex on macOS, filed as LAD-302.

## Residual risk

- The pull request changes `runtime.py` and `project_secrets.py`; `make test-live` not
  run.
- The manual check's Docker step and the human's manual check not done.
- LibreSSL/GnuTLS with an intermediate authority not checked.
- The handshake does not go through `HTTPS_PROXY`.
- That the F13 test is red without the fix rests on the developer's word.
