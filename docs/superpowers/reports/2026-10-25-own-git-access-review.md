# LAD-115 own-git-access: review report

Pull request #170 `hotfix/lad-115-git-access-from-secrets` → `main`. Scale: hotfix, planned
for precision, reviewed for breadth in round 1 (the diff touches the agents' environment
and a project's secrets). Head reviewed last: `77bea1e2` (= the remote head), base
`7343e07b`. The change gives LADO's own network git calls (kits, skill packs,
marketplaces, the listing and clone of a URL) the outside folder's variables, and a clone
into a project the project's variables and secrets: `agent_env.for_git`,
`project_secrets.layer`, `gitcache`, `clone`, the server's `/api/remote-branches`
(`RemoteAsk.project`), the project page, a container test, docs. `runtime.py`
(`_base_env`) and `agent_env.py` changed, so the human may want live tests before the
merge; `providers/`, `hooks.py`, `mcp_server.py` and `tests/live/` unchanged. Schema
migration: no.

## Rounds

- **Round 1** (`7343e07b..2b1ba8c3`, the whole pull request): a local breadth pass with
  the lenses spec, tests, silent failures, comments and general, and the supervisor's
  points: the move of `_base_env` is clean (no assertion of an existing test changed);
  secrets reach only the env of the git process, never an error text or the API answer
  (`public_remote`, the hint names `GH_TOKEN`, not its value); `LC_ALL=C` and
  `NO_PROMPT` for the kits' git keep the kinds recognised (probed by hand under
  `LANG=de_DE`); the API types are fresh, an unknown project is 404 before git runs.
  **External 1** (Claude Code GitHub Action, request comment 6401174823 at 18:01:18Z,
  "Claude finished" at 18:02:38Z, answer comment 6401230454): E1-E4. The external
  reviewer read `agent_env.py`, `runtime.py` and `server/app.py` by hunks only; the
  local pass read them whole.
- **Round 2** (`2b1ba8c3..77bea1e2`): a return after `merge_ok`, as the archive failed
  `openspec validate --specs --strict` (two `session-clone` requirements over 500
  characters). The environment's layers are now given by reference to `agent-variables`,
  and the three GitHub login hints moved word for word to the new requirement "A GitHub
  login hint names where LADO can take a token" with their scenarios. A precision pass
  over the spec delta and a trial archive in a copy of `openspec/`. No external round:
  the hotfix cap (1 of 1) was used and the code did not change.

External rounds used: 1 of 1. The external reviewer is of the same model family, so its
"nothing blocking" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| E1 | 1 | external 1 | a non-URL together with an unknown project is 400, not 404 | refuted | — | both refusals come before git runs (`server/clones.py`); the spec sets no order of refusals for a bad URL |
| E2 | 1 | external 1 | a kit's git failure is one line instead of git's whole stderr | refuted (by design) | — | AC-4 asks for one line; probes on a missing path, an unreachable host, an ssh host and a missing GitHub repository all give the reason, git's `fatal:` line and the hint |
| E3 | 1 | external 1 | the kits' git now runs with `GIT_ASKPASS=""` and `LC_ALL=C`, so an askpass helper is no longer asked | refuted (by design) | — | design D3: the kinds need `LC_ALL=C`; no prompt is the clone's rule too |
| E4 | 1 | external 1 | the hint names the outside folder's path | refuted | — | shown only for `login_needed` on github.com, as the spec's table says |

## Checked against the spec

AC-1 to AC-6 hold; every requirement and scenario of the `agent-variables` and
`session-clone` deltas is covered by code and a test; every task of `tasks.md` checked;
D1-D6 kept; nothing out of scope. The pull request's description matches the diff.

## Checks

Round 1: `make lint` 0; `make test` 4295 passed, 2 skipped; `openspec validate
own-git-access --strict` valid; `openspec validate --specs --strict` 48 passed; the API
types match the server. Round 2: the change valid; the trial archive then `openspec
validate --specs --strict` 48 passed, 0 failed; CI on `77bea1e2` 23 of 23 success,
`ci-ok`, container amd64/arm64 and smoke included.

## Not checked

`make web`, the UI tests and the container test locally (green in CI; no Docker here).
A real private GitHub repository with a real token (CI has no token; a manual check at
the release candidate). Live tests not run.
