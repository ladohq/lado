## 1. Tests first (unit, `tests/test_doctor.py`)

- [ ] 1.1 Scenarios "Claude Code not logged in" and "Codex not logged in on OpenAI's
  models": the three quotes of the old line (`test_check_logins…` for Codex,
  `test_claude_not_logged_in_warns_where_to_log_in` for the check and for the `[warn]`
  line `doctor.main()` prints) expect `not logged in: only its agents on your model
  server's models start; log in in Settings → Agent CLIs for its own models`. Red before
  2.1. The other doctor tests (`none`, keyring, `unknown`, `ok`) stay as they are.

## 2. The fix

- [ ] 2.1 `src/lado/doctor.py`, `login_check`: the `found.needs_login` branch returns that
  text, built with `logins.SETTINGS`; level `WARN`. 1.1 passes.
- [ ] 2.2 `docs/cli.md`, the `lado doctor` login paragraph: quote the new line in place of
  `new sessions and workers of it are refused, a resumed agent waits (Settings → Agent
  CLIs and environment)`.
- [ ] 2.3 CHANGELOG.md: add `## 0.45.1 (unreleased)` on top with a Fixed item: `lado
  doctor` no longer says that a CLI without its login cannot start; it says that its
  agents on your model server's models start (docs/release.md's item rules).

## 3. Checks

- [ ] 3.1 `make lint`, `make test`, `openspec validate doctor-login-line-server-models
  --strict` and the trial archive of `.lado/sdlc.md` pass; `grep -rn "are refused, a
  resumed agent" src docs tests` finds nothing.
