# LAD-290 git-servers-page: review report

Pull request #321 `feature/lad-290-git-servers-page` → `main`. Scale: full. Head reviewed:
`5ef265ec`. Settings → Git servers lists, adds and removes git servers over the UI server's
API, which takes the token only in the request's body and never returns it; the kind is
found as `lado git-server add` finds it, with a manual choice only when the server does not
answer. One server per host name (the CLI and the API refuse a second port on the same
host), and `git-servers/` goes with the last server.

## Rounds

1. Local, a full pass over `origin/main...af4781ef`, all lenses and the architecture
   against AGENTS.md. Found F1, F2 (important) and F3 (minor).
2. Local, precision, over the delta `af4781ef..5ef265ec`: F1 and F2 resolved, nothing new.
3. External 1, Claude Code GitHub Action (2026-11-16): five notes E1–E5, no blocker or
   important. It read the risky files of the diff (`git_servers.py`, `state.py`, `app.py`,
   `models.py`, `git_kinds/*`, `cli.py`, `api.ts`, `git_entries.py`, `GitServers.tsx`), not
   the tests or docs.

External rounds used: 1 of 2. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | local: the address check on the real gitlab.com answered "as GitHub and as GitLab"; the form showed a choice of kind instead of "Looks like GitLab" | fixed in `a2419fa9`, `5ef265ec`: each kind recognises only its own refusal; tests `test_gitlab_com_refusing_github_s_path_too_is_told_gitlab`, `test_github_s_refusal_is_told_by_its_documentation_link`, UI fake profile `gitlab-com`; checked against the real gitlab.com |
| F2 | important | local: a wrong token on gitlab.com without a chosen kind was named GitHub's refusal, with GitHub's token page | fixed in the same commits; checked against the real gitlab.com |
| F3 | minor | local: a server gone between the address check and Add asks to choose a kind the form does not show | declined: rare; editing the address runs the check again |
| E1 | — | external: pairs on one host saved before this change are refused when added again | refuted: no released version could save such a pair |
| E2 | minor | external: a host name with a trailing dot escapes the one-host rule | declined: the address parsing is older; rare input |
| E3 | minor | external: a remove racing a replace of the same server may leave it without a token file | declined: narrow window; the page shows the missing token file |
| E4 | minor | external: a disk refusal removing `git-servers/` reports an error after the server is gone | declined: cosmetic, the text is true about the folder |
| E5 | — | external: the page sends the token without trimming spaces | refuted: the page keeps the CLI's rule (one trailing newline dropped) |

## Metrics

Rounds: 2 local, 1 external, 0 stand-ins. Findings: local 3 confirmed (2 important, 1
minor), 0 refuted; external 3 confirmed (minor, declined), 2 refuted; findings in code
changed by the developer's cleanup: 0.

## Checks

- Round 2, on `5ef265ec`: `make lint` clean; unit tests of git servers, CLI, API, fake and
  `tests/test_git_kinds.py` 161 passed; integration `test_git_server_access.py` 2 passed;
  UI `test_git_servers_section.py` 1 passed; read-only probes of gitlab.com and
  api.github.com.
- Round 1, on `af4781ef`: `make lint` clean; unit 157 passed; UI Git servers and Settings
  17 passed; `openspec validate` valid, `--specs` 86, trial archive 87.
- CI of PR #321 on `5ef265ec`: 27 of 27 pass, `ci-ok` included.

## Residual risk

- A self-hosted GitLab and GitHub Enterprise answering without a token are not checked
  live; only gitlab.com and api.github.com.
- No change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
  `tests/live/`: no live tests needed.
