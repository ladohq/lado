# LAD-168 codex-login-code: review report

Pull request #191 `fix/lad-168-codex-login-code` → `main`. Scale: tweak. Head reviewed
last: `e3955bca` (= the remote head). Codex's login window ("Get a sign-in code") shows no
terminal: the Codex provider reads the link, the one-time code and Codex's warning from
`codex login --device-auth`'s output, and the window shows "Open sign-in page", the code
with "Copy code" (the legacy copy over plain http too) and, on a computer, a QR code of the
link; when Codex ends without a login, its last line stays with "Get a new code"; when the
link and the code are not found within 10 seconds, Codex's terminal is shown. The window's
command runs through a wrapper (`python -m lado.logins`) that writes its exit status to a
file. `providers/` (base, codex) changed; the login command runs through LADO's wrapper.

## Rounds

- **Round 1** (`origin/main...7b75b8c9`): a local pass in breadth (spec, tests, silent
  failures, comments, types, general, architecture against AGENTS.md). F1 blocker, F2
  important, F3-F6 minor.
- **Round 2** (`7b75b8c9..e3955bca`, commits `5b69ddfd`, `e93ee021`, `14684b4c`,
  `e3955bca`): a local precision pass over the fixes. F1 and F2 resolved; F7 minor.
- **External round 1** (Claude Code GitHub Action, 43 s): no blocker; F8, F9 new, an
  addition to F3, a repeat of F7. It read the changed lines of all 5 risky files only, not
  the tests, `web/` or openspec, and ran no tests.

External rounds used: 1 of 1 (tweak). The external reviewer is of the same model family,
so its "no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | blocker | A successful login showed as a failure: tmux under load reports a dead pane before its `pane_dead_status`, so the window was read with no status and killed | fixed in `14684b4c`: the command's wrapper writes its exit status to a file, tmux's status the fallback; UI test 8 of 8 in 8 parallel runs, CI `ui (1)`, `ui (2)` green |
| F2 | important | The change's spec, design and tasks differed from the code ("Codex" for "Codex CLI", `expires` missing from D4, a wrong test file in task 1.1) | fixed in `e93ee021`, `e3955bca` |
| F3 | minor | The `prompt` frame is sent once: a snapshot between the code and the warning, or a half-printed code, would stay until a reconnect | declined: Codex prints the block in milliseconds against a 0.5 s poll; a reconnect sends the whole prompt |
| F4 | minor | Two tabs on one window: only the first gets `ended` | declined: rare (the QR code leads to OpenAI, not to LADO) |
| F5 | minor | "…sign in to ChatGPT" in the neutral `LoginWindow.tsx` | declined: set by the spec; only Codex `shows_code` today |
| F6 | minor | OpenCode's and Kilo's windows show tmux's "Pane is dead" for up to 0.5 s | declined: cosmetic |
| F7 | minor | Stale comments and a fixture about `pane_dead_signal` | declined: wording only |
| F8 | minor | external: a browser gone during `logins.look` loses `ended` | declined: a narrow window, akin to F4 |
| F9 | minor | external: a `Popen` error other than a missing program leaves a traceback and no status file | declined: tmux's status is the fallback; `check_program` checks the program first |

## Checks

- On `e3955bca`: `make lint` green; `make test` 4706 passed, 7 skipped; integration
  `test_provider_logins` 14 passed; UI `test_providers_section` 8 passed in each of 8
  parallel runs; `openspec validate codex-login-code --strict` and
  `openspec validate --specs --strict` valid; CI 23/23 with `ci-ok`, UI, smoke and
  container.
- `make web` in round 1 (1159 passed); `web/` unchanged since.

## Residual risk

- A real Codex failure (the code expiring after 15 minutes) and a physical phone over the
  LAN were not checked by hand; the developer's manual run with real Codex 0.162.0 over
  http passed, also after the wrapper.
- No live tests ran, though `providers/` changed and the login command now runs through
  LADO's Python wrapper in the agents' environment.
- The external reviewer read only the changed Python lines; `web/`, tests and openspec
  were reviewed locally only.
- For the human: the window's texts say "Codex CLI" (the provider's name), not "Codex" of
  the approved mockup.
