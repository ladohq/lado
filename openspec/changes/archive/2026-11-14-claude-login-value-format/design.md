## Context

Claude Code's login sheet keeps a pasted value as LADO's secret through
`PUT /api/providers/{name}/variables/{variable}` (`src/lado/server/app.py`,
`set_login_variable`), which calls `logins.check_secret` and then
`project_secrets.write_lado`. `check_secret` knows the variable's name and the value's size
and encoding only.

## Decisions

### D1. A provider hook, called by `check_secret`

`Provider.login_value_problem(self, variable: str, value: str) -> str | None` in
`providers/base.py`, returning `None` by default; its docstring says it is asked before a
value pasted for one of `login_variables` is kept, and returns a sentence for the human.
`logins.check_secret` calls it last, after its own checks (name, empty, `value_problem`), and
raises `ValueError` with the sentence; the endpoint already turns a `ValueError` into 400 with
its text, which the sheet shows. Why: the prefixes are Claude Code's facts and stay in
`providers/claude.py`; any caller of `check_secret` gets the check.

### D2. Spaces and line breaks around the value are dropped by the endpoint

`set_login_variable` strips the value (`str.strip()`) before `check_secret` and
`write_lado`; a value of spaces only is then empty and refused as today ("needs a value").
Only the login endpoint strips: a project's secrets keep their values whole, as their
spec says. Why: a token copied from a terminal often carries a line break or spaces around
it; no token or key has them.

### D3. Claude Code's formats

In `providers/claude.py`, next to `TOKEN`:

- a subscription token: `sk-ant-oat\d+-` then `[A-Za-z0-9_-]+` to the end;
- an API key: `sk-ant-api\d+-` then `[A-Za-z0-9_-]+` to the end.

Any version digits are accepted, so a new version of a prefix does not lock people out; the
messages name today's prefixes (`sk-ant-oat01-`, `sk-ant-api03-`). No length check: the
lengths are not documented. `login_value_problem` for `TOKEN` and for `ANTHROPIC_API_KEY`
(any other variable: `None`), in this order:

1. the value matches its own variable's format: `None`;
2. it starts with its own prefix (`sk-ant-oat\d+-` / `sk-ant-api\d+-`) but does not match:
   the characters message (AC-4);
3. it matches the other variable's format, or starts with the other's prefix: the "other
   choice" message (AC-2), naming the other choice by its title from `login_choices`;
4. anything else: the "not a token" / "not an API key" message (AC-1, AC-3).

The messages are the exact texts of the proposal's acceptance criteria; they quote no part
of the value, only the fixed prefixes.

### D4. No change of the web UI or the API models

The sheet already shows a 400's `detail` under its choices with `role="alert"` and keeps the
sheet open with the value still in the field; `web/openapi.json` does not change (the
answer is the same `HTTPException`).
