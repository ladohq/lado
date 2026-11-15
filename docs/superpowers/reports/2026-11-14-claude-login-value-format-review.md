# LAD-170 claude-login-value-format: review report

Pull request #310 `fix/lad-170-claude-token-format` → `main`. Scale: tweak, depth precision.
Head reviewed: `e931a217`. A string of the wrong format pasted into Claude Code's login sheet
was saved as `CLAUDE_CODE_OAUTH_TOKEN` and shown as logged in until an agent's first turn
failed with 401. The provider hook `Provider.login_value_problem` (default `None`) now lets
Claude Code's provider refuse, through `logins.check_secret`, a value that is no subscription
token (`sk-ant-oat<digits>-…`) or API key (`sk-ant-api<digits>-…`), or one of the other kind;
the login endpoint strips spaces and line breaks around the value first. The server answers
400 and the sheet shows the refusal it already showed.

## Rounds

1. Local, precision, over `origin/main...e931a217` (commits `223dc125..e931a217`), by hand and
   with the lenses spec, tests, silent failures and comments; types skipped (no new types).
2. External 1, Claude Code GitHub Action (request 20:15:22Z, "Claude finished" 20:19). It read
   every code and test file of the diff and the spec; not the docs, CHANGELOG, proposal,
   design or tasks (checked locally).

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | local: `\d` in the prefixes matches non-ASCII digits, so `sk-ant-oat١-abc` is accepted | declined: no real paste holds such digits; a one-character fix (`[0-9]`) if the human wants it |
| F2 | minor | local: `sk-ant-oat01-` with nothing after it gets the "characters it cannot have" text, though it is a cut paste | declined: the order of D3, step 2 |
| E1 | — | external: a value of the other kind with a space inside gets the "other choice" text, not "copy it again" | refuted: D3 step 3 says "or starts with the other's prefix"; a test pins it |
| E2 | — | external: nothing pins that the hook runs after `agent_env.value_problem` | refuted: `test_a_value_the_agents_could_not_get_is_refused[nul]` expects "is not UTF-8 text" for `sk-ant-oat01-canary\0x` |
| E3 | — | external: a token saved before is not checked | refuted as a defect: out of scope (part (b) of LAD-170) |

## Metrics

Rounds: 1 local, 1 external, 0 stand-ins. Findings: local 2 confirmed (both minor, declined),
0 refuted; external 0 confirmed, 2 refuted, 1 out of scope; findings in code changed by the
developer's cleanup: 0.

## Checks

- `make lint`: green.
- `make test`: 6170 passed, 7 skipped.
- `openspec validate claude-login-value-format --strict`: valid.
- CI on `e931a217`: all jobs green, `ci-ok` pass.
- At archive: `openspec validate --specs --strict`: 84 passed.

## Residual risk

- Integration, smoke and container tests were not run locally; CI ran them, green.
- Live tests were not run (paid models). The change touches `src/lado/providers/` (`base.py`,
  `claude.py`), but the hook runs only in the login sheet's endpoint and does not change how
  agents start.
