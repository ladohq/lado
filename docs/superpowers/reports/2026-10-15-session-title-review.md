# LAD-66 session-title: review report

Pull request #51 `feature/lad-66-session-title` → `main`. Scale: full, reviewed for
breadth first, at most two external rounds. Head reviewed last: `a8e6d27` (= the remote
head); the archive commit follows it. `providers/`, `hooks.py`, `mcp_server.py`,
`agent_env.py` and `tests/live/` did not change; `runtime.py` got only the pure rule
`set_title` and `MAX_TITLE`, so live tests are not needed before the merge.

## Rounds

- **Round 1, local** (breadth over `origin/main...2b9633a`: spec, tests, silent failures,
  comments, types, general, and the architecture against AGENTS.md): F1, F2.
- **Round 2, local** (precision over `2b9633a..a8e6d27`: `Sessions.tsx`'s `initials`, two
  tests in `Layout.test.tsx`): F1 refuted, F2 resolved, no new finding.
- **Round 1, external** (Claude Code GitHub Action, request 2026-10-14T22:14:50Z, answer
  22:15:43Z, on `a8e6d27`; it read the code and ran no tests): E1, E2, E3, all minor,
  confirmed and declined. The answer is posted on the pull request. The external reviewer
  is of the same model family, so its "nothing blocking" weighs less.

External rounds used: 1 of 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (general) | the head's title field outlives a switch of session and saves session A's text into B | refuted | — | dropped: the whole `SessionView`, the head with it, sits under `<TerminalPanel key={name}>` (`web/src/Sessions.tsx`) and remounts on a switch; the developer's regression test in `Layout.test.tsx` stays |
| F2 | 1 | local (general) | `initials` took a UTF-16 unit: a title that starts with an emoji gave a lone surrogate | confirmed | minor | fixed in `a8e6d27` with a test in `Layout.test.tsx` |
| E1 | ext. 1 | external | `PUT …/title` answers 500 when the session is forgotten between `set_title` and `get_session` | confirmed | minor | declined: a race of the human's own two requests within milliseconds; no data is harmed |
| E2 | ext. 1 | external | U+2028/U+2029 (Zl, Zp) and bidi controls (Cf, e.g. U+202E) pass the rule | confirmed | minor | declined: the spec's rule is Cc, enough for one line; the title is the human's own label and React escapes it; whether to refuse Zl/Zp/Cf is the human's call |
| E3 | ext. 1 | external | after the server's refusal, the blur sends the same text again | confirmed | minor | declined: harmless, the same error shows |

## Checks

- On `a8e6d27`: `make lint` 0; `make web` 0, 762 vitest passed; CI of PR #51 21/21
  green, `ci-ok` and the smoke included.
- On `2b9633a`: `make test` 3143 passed; UI e2e (head, list, launch) 30 passed;
  `openspec validate --specs --strict` and `session-title --strict` valid. The last delta
  changed no Python; the developer's `make test` on `a8e6d27` gave 3143 passed.

## Not checked (residual risk)

- `make test-integration` as a whole and `make test-smoke` were not run locally; CI ran
  them, green.
- `make test-live` was not run: no provider, hook, MCP or agent environment code changed.
- The 27 → 28 migration is covered by unit tests and, by the developer's word, by hand on
  a copy of a real database; the reviewer did not repeat the manual check.

## Found on the way

- None.
