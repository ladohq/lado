Task: LAD-170

## Why

Symptom (manual check of 0.44.0rc1): a string of the wrong format (92 characters, neither
`sk-ant-oat01-` nor `sk-ant-api03-`) pasted into Claude Code's login sheet under
"Subscription — Claude Pro or Max" was saved as LADO's secret `CLAUDE_CODE_OAUTH_TOKEN`.
Settings and `lado doctor` then said "Logged in · Subscription (token) · LADO's secret",
and the first turn of the agent failed with `API Error 401 Invalid bearer token`
(`authentication_failed` in the chat).

Cause: the sheet's Save (`PUT /api/providers/{name}/variables/{variable}`) checks a value
only by `logins.check_secret`: one of the provider's login variables, not empty, UTF-8 of
at most 64 KiB. Nothing looks at what the value is. `claude auth status --json`, which
Settings and doctor read, does not check a token with Anthropic's server: any non-empty
`CLAUDE_CODE_OAUTH_TOKEN` is `loggedIn` with `authMethod: "oauth_token"`. So a value
that can never work is shown as a working login until an agent runs.

Options weighed:

- Taken: the provider checks the format of a pasted login value before it is saved
  (`Provider.login_value_problem`, Claude Code's by the prefixes of a subscription token
  and an API key); the server refuses a value with a problem with 400, and the sheet shows
  the refusal it already shows today. Long-term cost: Claude's prefixes live in one place
  of `providers/claude.py`; a new version of a prefix is accepted by itself (D3).
- A check in the web UI only: a provider detail above `providers/` (neutral core), and a
  request that skips the UI saves anything; rejected.
- A network check of the token with Anthropic on Save: it proves the token works, but it
  sends a request from the server on each Save, needs the network and an endpoint to call,
  and belongs to the wider question of how LADO learns that a login does not work (part
  (b) of the task, left out below); rejected for this change.

## What Changes

- A neutral provider hook, `Provider.login_value_problem(variable, value) -> str | None`:
  why a value pasted for one of the provider's login variables cannot be its login, `None`
  by default.
- Claude Code's provider answers for `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_API_KEY`: a
  subscription token is `sk-ant-oat<digits>-` and an API key `sk-ant-api<digits>-`, each
  followed by one or more letters, digits, `-` or `_`. A value of the other kind is
  refused with a pointer to the other choice; any other value with what is expected and
  where it comes from (`claude setup-token`, console.anthropic.com).
- `logins.check_secret` calls the hook after its own checks; the sheet's Save strips
  spaces and line breaks around the pasted value before checking and saving it.
- `docs/design/ui.md` (the login sheet) and CHANGELOG.md say so.

## Scope

Claude Code's login sheet in Settings (Agent CLIs), through the server's
`PUT /api/providers/{name}/variables/{variable}`: both of its fields, the subscription
token and the API key.

## Out of scope

- Part (b) of LAD-170: a login that fails in a running agent (`authentication_failed` of
  Claude Code, `refresh_token_reused` / 401 of Codex) shown as not working in Settings and
  doctor. The human set it aside to be decided together with LAD-171.
- A token saved before this change, or set elsewhere (a project's variable or secret, the
  outside folder, the login shell, `lado project set --secret`): not checked; Settings and
  doctor still read it with `claude auth status`. Showing a known-bad saved token belongs
  to part (b).
- Codex's fields (access token, OpenAI API key): the human chose Claude Code only; Codex
  keeps the hook's default.
- A "save anyway" choice: the human chose a hard refusal; future versions of the prefixes
  are accepted (D3), and keys of proxies or gateways are not entered through this sheet
  (model servers have their own key).
- Saving a value of the other kind under the other variable silently: the human would not
  see that the way they pay changed.

## Acceptance criteria

- AC-1: In Claude Code's sheet, Save under "Subscription — Claude Pro or Max" with a value
  that is no subscription token and no API key answers 400, writes no secret, keeps the
  sheet open and shows "This is not a Claude subscription token: a token starts with
  sk-ant-oat01-. Run claude setup-token and paste the whole token it prints."
- AC-2: An API key (`sk-ant-api03-…`) saved under Subscription is refused with "This is an
  API key (sk-ant-api03-…), not a subscription token: to pay per use with it, choose “Pay
  per use — API billing”."; a subscription token saved under "Pay per use — API billing"
  is refused with "This is a subscription token (sk-ant-oat01-…), not an API key: to use
  your subscription, choose “Subscription — Claude Pro or Max”."
- AC-3: Any other value saved under Pay per use is refused with "This is not an Anthropic
  API key: a key starts with sk-ant-api03-. Create one at console.anthropic.com → API keys
  and paste it whole."
- AC-4: A value with the right prefix but a character no token has (a space or a line
  break inside it, other punctuation) is refused with "This token or key has characters it
  cannot have (a space or a line break?): copy it again as one line." (the same text for
  both fields).
- AC-5: A valid token or key, also with spaces or line breaks around it and with another
  version digit (`sk-ant-oat02-…`), is saved without them, as today; no refusal and no log
  line contains the value or a part of it after its prefix.
- AC-6: Other providers' login variables are saved as before (the hook's default).
- AC-7: `make lint`, `make test` and the UI test of the providers section pass.

## Impact

- `src/lado/providers/base.py`, `src/lado/providers/claude.py`, `src/lado/logins.py`,
  `src/lado/server/app.py`; unit tests in `tests/test_providers.py`, `tests/test_logins.py`,
  `tests/test_server_providers.py`, and the test values of Claude's login variables there and
  in `tests/ui/test_providers_section.py` (they become values of the right format).
- No API model, schema, MCP or CLI change; no change of `web/` code (the sheet already shows
  a 400's text and stays open, `LoginSheet.test.tsx` "a refused value is said and the sheet
  stays").
- CHANGELOG.md: a line under `### Fixed`; a patch-level change.

## Decisions for the record

- Scale tweak: a small change of known shape (one provider check, called where the value is
  already checked); review by precision.
- The check is the provider's (neutral core): the server and the UI know no prefix; Codex,
  Kilo and OpenCode keep the default `None`.
- Refused on the server, shown by the sheet's existing refusal: one source of truth, also
  for a request that does not come from the UI.
- Test layer: unit (the provider's check, `check_secret`, the endpoint through the test
  client); the sheet's display of a 400 is already a Vitest test; no integration test, as
  nothing crosses processes.
