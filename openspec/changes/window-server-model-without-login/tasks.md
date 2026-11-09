## 1. The providers list (server)

- [x] 1.1 `tests/test_server_launch.py` (unit): failing tests first. Claude Code not logged in with a
  saved model `CloudClaude` (not its default) → `login_missing: true`, `starts_on_server: true`;
  the same model as its default → the same (replaces
  `test_claude_code_with_a_default_on_a_server_is_not_missing_its_login`); no saved model →
  `starts_on_server: false`; Codex with a model that needs a login and a saved model → true; Kilo
  or OpenCode with a saved model → both false; logged in → both false (AC-1, AC-2).
- [x] 1.2 `src/lado/server/models.py` `ProviderInfo.starts_on_server: bool = False` with its comment;
  `src/lado/server/launch.py` `provider_infos`: `login_missing` without the default-on-server case,
  `starts_on_server` by design D1 (saved models read once, outside the threads; `has_db` false →
  none); docstring updated. Tests of 1.1 pass.

## 2. The window's check of a model (server)

- [x] 2.1 `tests/test_server_launch.py` (unit, beside the other `CHECK` tests): failing tests first.
  Claude Code not logged in: `opus` → `kind: refused`, `login: true`, the text, `short` and `peek`
  of design D2; `CloudClaude` → `ok` and no login status read; logged in: `opus` → no `login`
  (AC-4).
- [x] 2.2 `src/lado/server/models.py` `SessionModelCheck.login: bool = False`;
  `src/lado/server/model_entries.py` `check_session_model` calls `runtime.check_login` after the
  model's check for a start with no server, a `NotLoggedIn` its refusal (design D2). Tests of 2.1
  pass.
- [x] 2.3 `make web-types`; commit `web/openapi.json` and `web/src/api.gen.ts`.

## 3. The window (web)

- [ ] 3.1 `web/src/LaunchTeam.tsx` and `web/src/Launch.tsx`: the option, `held`, the notes under
  Agent, `canStart` and the footer by design D3. Vitest in `LaunchTeam.test.tsx` and
  `Launch.test.tsx`: the option's text and enabled state with and without `starts_on_server`; a
  suggested CLI with it is taken; the plain note and its `Log in` link; no `log in to` in the
  footer; without it everything as before (AC-1, AC-2, AC-6).
- [ ] 3.2 `web/src/LaunchModel.tsx`: the CLI's `login_missing`/`starts_on_server` passed in; the
  refusal of the CLI's settings, the one-model pick of a new session, and `Use <name>` / `Log in
  first` on a refusal with `login` by design D4. Vitest (fakes in `fakes.ts`/`modelFakes.ts`): one
  saved model is taken with its note; two are not and the field is refused; a resume keeps its
  kept model; a human's change is not undone; `opus` refused shows both ways out and not `Use
  Claude Code's settings`; logged in, nothing changes (AC-3, AC-5, AC-7).
- [ ] 3.3 `web/src/ModelPicker.tsx`: `needsLogin` and the `needs login` marks by design D5. Vitest
  in `ModelPicker.test.tsx` (AC-5).
- [ ] 3.4 `make web` passes (stale-types check, tsc, vitest, build).

## 4. End to end (UI)

- [ ] 4.1 `tests/ui/test_launch.py` (marker `ui`): the fake agent `fake-login` not logged in with one
  saved model on the fake model server: New session offers it with `not logged in: your server's
  models only`, the field holds the model, Start is on and the session starts on it; picking a
  built-in model shows the refusal and `To start: fix the model`. When the fake agent cannot run on
  a server in this layer, the test ends at Start on and the build report says so (the start itself
  is covered by `tests/integration/test_claude_model_server.py`). Screenshots of both states at
  1280 px as run artifacts (AC-1, AC-3, AC-5).
- [ ] 4.2 `test_a_cli_without_its_login_is_greyed_out_and_leads_to_settings` and
  `test_resume_without_the_login_is_disabled_and_leads_to_settings` still pass unchanged (AC-6).

## 5. Docs and the regression run

- [ ] 5.1 `docs/design/ui.md`, Launch and session control: the Agent option and note for a CLI that
  starts on a server without its login, the Model field's refusal, marks and one-model pick, and the
  Resume paragraph's `not logged in` case (LAD-255).
- [ ] 5.2 The settings' Checks: `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_launch.py`, `openspec validate window-server-model-without-login --strict` and the
  trial archive; no CHANGELOG line (design D7).
