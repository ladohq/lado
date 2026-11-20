# LAD-303 git-server-host-tool: review report

Pull request #342 `feature/lad-303-git-server-host-tool` → `main`. Scale: full. Head
reviewed: `74bef292`. LADO's image ships `glab` 1.130.0; each agent gets its own `glab`
configuration with one entry per saved GitLab (host, protocol, path, that host's
certificate), its token sent as a `PRIVATE-TOKEN` header read from the token file on each
call; GitLab variables from outside do not reach agents and doctor names them. An agent
whose `origin` is on a saved server gets one line naming the server's kind and tool (`gh`
or `glab`); a missing or too old tool warns loudly at launch and in doctor, and a GitLab
token without `api` is named by Check, `add` and doctor.

## Rounds

1. Local, breadth first over `origin/main...87b9c670`: spec, tests, silent failures,
   comments, general/security, and the architecture against AGENTS.md. Found F1–F4.
2. Local, precision on `87b9c670..74bef292`: the variable list in spec, design, docs and
   doctor; the new `OAUTH_TOKEN` warning; the new tests. Nothing new.
3. External 1, Claude Code GitHub Action on `origin/main...74bef292` (request comment
   7021687288, answer 7021693728): read every risky file of the diff, not the tests, docs
   or openspec. Found F5, F6.

External rounds used: 1 of 2. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | `GITLAB_API_HOST` from a layer sent a saved GitLab's requests with its `PRIVATE-TOKEN` header to another host; `GITLAB_REPO` pointed `glab` at another project | fixed in `8ff84643`: both dropped and named by doctor; integration test with the real `glab`, no request reaches a third host |
| F2 | minor | the requirement on the `add` line for a token without `api` asked for a full stop the code does not write | fixed in `8ff84643` (spec wording) |
| F3 | minor | the other-host test did not tell a certificate refusal from a 401 | fixed in `74bef292`: the full URL from server A's repository goes without the token (401); outside a repository the call fails on `x509: certificate signed by unknown authority` |
| F4 | minor | an unreadable `--version` counts as a fitting tool, so the agent is told it is logged in | declined: design D5 (no false alarm); in the image `/opt/tools/bin` precedes the shims |
| F5 | minor | the agent's line says "logged in already" for a GitLab whose token lacks `api` | declined: LADO does not know the token's scopes at launch; Check, `add` and doctor name it |
| F6 | minor | `--version` runs on every spawn; a hung binary delays it up to 10 s | declined: design D5, bounded by the timeout |

## Metrics

- Rounds: 2 local, 1 external, 0 stand-ins.
- Confirmed: local 4 (1 important, 3 minor), external 2 (minor).
- Refuted: 0.
- Findings in code changed by the developer's cleanup: 0.

## Checks

- Round 2 at `74bef292`: `make lint` clean; `make test` 6025 passed, 14 skipped;
  `tests/integration/test_git_server_host_tool.py` with the real `glab` 1.131.0, 7 passed;
  `openspec validate git-server-host-tool --strict` valid; trial archive, 87 passed.
- CI of PR #342 at `74bef292`: 27/27, the container tests on amd64 and arm64 included.

## Found on the way

- Nothing.

## Residual risk

- The pull request changes `runtime.py`, `agent_env.py` and `tests/live/`; the live test
  `test_an_agent_pushes_through_a_saved_git_server` (Claude Code and Codex) is written,
  not run: it runs on the RC.
- The container tests were not run locally (green in CI); smoke runs in CI only.
- The human's manual check on a real company GitLab (Docker on a Mac, VPN) is left for
  the RC, steps 0–8 of the pull request's description.
