## 1. The check

- [ ] 1.1 `src/lado/providers/base.py`: `Provider.login_value_problem(variable, value) ->
  str | None`, `None` by default, with a docstring (D1). Unit test in
  `tests/test_providers.py`: a provider without an override returns `None` (AC-6).
- [ ] 1.2 `src/lado/providers/claude.py`: the two formats next to `TOKEN` and
  `login_value_problem` by D3's order with the exact texts of AC-1..AC-4. Unit tests in
  `tests/test_providers.py`, one per branch: a valid token and key (also `oat02`/`api04`),
  a key under `TOKEN`, a token under `ANTHROPIC_API_KEY`, no prefix under each, a right
  prefix with a space / a line break / `+` inside, another variable name (`None`); each
  refusal is checked not to contain the value's part after its prefix (AC-1..AC-5).
- [ ] 1.3 `src/lado/logins.py`: `check_secret` calls the hook last and raises `ValueError`
  with its text; docstring updated (D1). Unit test in `tests/test_logins.py` (refused for
  Claude, a Codex value accepted as before) (AC-6).

## 2. The endpoint

- [ ] 2.1 `src/lado/server/app.py` `set_login_variable`: strip the value before
  `check_secret` and `write_lado` (D2). Unit tests in `tests/test_server_providers.py`: a
  value of no format answers 400 with AC-1's text and writes no file; a valid token with
  `"\n"` and spaces around it is saved stripped (file content checked), the row "Logged in";
  spaces only answer "needs a value" (AC-1, AC-5).
- [ ] 2.2 Existing tests that save Claude's login variables with made-up values
  (`tests/test_server_providers.py` "c-5", "canary-1", "canary-tok", "canary-key", the 64 KiB
  and UTF-8 cases; `tests/ui/test_providers_section.py` "canary-ui-token") use values of
  the right format (the canary text after the prefix), every assertion kept; the size and
  encoding cases still get their own refusals, since the hook runs after them.

## 3. Docs and checks

- [ ] 3.1 `docs/design/ui.md`, the login sheet: Save refuses a value that is not of the
  choice's format (Claude Code: the subscription token's and the API key's prefixes), drops
  spaces and line breaks around a value, and the refusal shows under the choices.
- [ ] 3.2 CHANGELOG.md under `## 0.47.0 (unreleased)` → `### Fixed`: "**Claude Code's login
  checks what you paste.**" — a string that is no subscription token or API key, or one of
  the other kind, is refused with what to paste instead, rather than shown as logged in.
- [ ] 3.3 `make lint`, `make test`, `uv run pytest -m ui
  tests/ui/test_providers_section.py`, `openspec validate claude-login-value-format
  --strict` and the trial archive pass (AC-7).
