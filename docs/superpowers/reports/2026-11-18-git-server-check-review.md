# LAD-293 git-server-check: review report

Pull request #324 `feature/lad-293-git-server-check` → `main`. Scale: full. Head reviewed:
`0a0f06b2`. A saved git server can be checked with its token (`lado git-server check` and
Check on Settings → Git servers), the check names the token's missing scopes, and the
screen follows the approved layout: per-server panel with sign-in, commit author (with
Undo) and removal, Replace token, explanations behind ⓘ, one result line at a time.

## Rounds

1. Local, a full pass over `origin/main...c71ad8ad`; the web UI checked against the spec
   by a helper, each of its findings verified against the code. Found F1–F10.
2. Local, precision, `c71ad8ad..655e34f4`: F11 (brought by the fix of F3).
3. Local, precision, `655e34f4..73e7b8f3`: nothing new.
4. External 1, Claude Code GitHub Action: E1–E5, no blocker or important.
5. Back after `merge_ok` (the human's manual check), local, precision,
   `73e7b8f3..7c935ae7`: the fixes are right; F12, F13 in the texts.
6. Local, precision, `7c935ae7..98eaa127` and the PR description: F12, F13 resolved.
   External 2, Claude Code GitHub Action, delta `73e7b8f3..98eaa127`: E6, E7, both minor.
7. Back after `merge_ok`: the archive failed strict validation (the requirement "A git
   server's address" grew over 500 characters). Local, precision, `98eaa127..0a0f06b2`,
   spec only: the character rule moved into its own requirement "An address with a space
   or a stray character is refused". Nothing new; a trial archive validated.

External rounds used: 2 of 2. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | a GitLab token without `read_api` (403 `insufficient_scope`) was told "expired or was revoked" | fixed in `655e34f4`: `scopes_missing` naming `read_api`; test in `tests/test_git_servers.py` |
| F2 | important | one `checking` flag for the whole page | fixed in `655e34f4`: a list of hosts; vitest |
| F3 | important | a late answer overwrote a newer result, moved focus, brought back a removed server; Cancel did not cancel the save | fixed in `655e34f4`: an action number, stale answers dropped; vitest |
| F4 | important | `Already saved.` without `Replace its token` for a server saved through `http://` or with a path | fixed in `655e34f4`: lookup by host key; vitest |
| F5 | important | "stopped answering" stayed after Try again | fixed in `655e34f4`; vitest |
| F6 | minor | Check answered 404 showed nothing | fixed in `655e34f4`; vitest |
| F7 | minor | the no-answer line of Replace token was built on the client | fixed in `655e34f4` |
| F8 | minor | `placeAbove` did not keep the tip inside the window at the top | fixed in `655e34f4`; `Menu.test.tsx` |
| F9 | minor | spec scenario said "5 seconds", the code "5 s" | fixed in `655e34f4` |
| F10 | minor | Replace token does nothing for a kind missing from `kinds` | declined: unreachable, `kinds` holds every core kind |
| F11 | important | after a stale answer the save form (Replace token, author, Add) stayed busy forever | fixed in `73e7b8f3`: closed by the form's identity; 4 vitest |
| F12 | important | the PR's short manual re-check named steps 4, 8, 11 instead of 3, 7, 10 | fixed in the PR description |
| F13 | important | the scenario "An expired token" included GitHub's `Bad credentials` and promised GitLab's line | fixed in `98eaa127`: GitHub has its own "A revoked GitHub token" |
| E1 | minor | a successful check fails with `Refused(LOCKED)` when another change holds the 10 s lock | declined: only short writes hold the lock |
| E2 | minor | a remote with a trailing dot in the host gets no token or author | declined: older behaviour, git matches `credential.<url>` literally |
| E3 | — | `savedHost` by `new URL().host` may differ from the key for a default port | refuted: same key for default ports and IPv6, checked by running |
| E4, E5 | — | not findings (spec-conform `role="alert"`; GitLab's `api` rule unchecked live, already a residual risk) | dropped |
| E6 | minor | a host saved before the new address rule would give `BadAddress` → 500 on check | declined: unreachable, git servers are not released yet |
| E7 | minor | document that a gateway answering OAuth `invalid_token` on every path is named GitLab | declined: an accepted trade-off, recorded here |

Also declined: author Remove and Undo are not disabled during their request (a repeat is
harmless); the `✓` prefix of `.gx-result.ok` also stands before `Works: …` (visual only).

## Metrics

- Rounds: 7; local 5 (plus the local pass of round 6), external 2, stand-ins 0.
- Confirmed: local 13 (8 important, 5 minor), external 4 (all minor).
- Refuted: local 0, external 1 (E3).
- Findings in code changed by fixes: 1 (F11, from the fix of F3).

## Checks

- Trial archive in a copy of `openspec/` at `0a0f06b2`: `openspec validate
  git-server-check --strict` valid, archive passed, `openspec validate --specs --strict`
  87 passed.
- CI at `0a0f06b2`: 27 successful, the pull request clean.
- At `7c935ae7`: `make lint` green; unit `test_git_servers`, `test_cli_git_server`,
  `test_server_git_servers` 338 passed; vitest GitServers/InfoTip/Menu 67 passed; `tsc
  --noEmit` green. The code did not change after.
- Flakes unrelated to the work: Kilo smoke on macOS (in BACKLOG.md, `8c194696`);
  `tests/test_tmux.py::test_send_text_pastes_multiline_text` at `98eaa127`.
- Not run by the reviewer: `make test` as a whole (the developer's 5896 passed, CI green),
  `make web` (CI green), `make test-live`, smoke (CI only).

## Residual risk

- A gateway answering 401 with an OAuth body `{"error": "invalid_token"}` on every path is
  named GitLab: one answer cannot tell them apart.
- GitLab's bodies for a revoked and an expired token come from the human's report and the
  documentation.
- "GitLab's `api` scope allows push over https" is from the documentation, not checked on
  a live server.
- A fine-grained GitHub token's permissions are not checked, by design.
- `make test-live` not run; `src/lado/runtime.py` changed by two lines, no provider
  touched.
