# LAD-304 git-servers-guide: review report

Pull request #345 `fix/lad-304-git-servers-guide` → `main`. Scale: tweak. Head reviewed:
`be50ae3a`. A plain-words guide, `docs/git-servers.md` ("Connect your git server"), from
making a token to the agents at work, with every answer of Check and what to do about it,
linked from docs/install.md; and the page's lines for a GitLab token without `api` (Check,
Add server, Replace token) now end with `; glab cannot open merge requests: the token
lacks api`, as the command's do. A unit test pins the guide's links and quoted answers to
the code.

## Rounds

1. Local, precision over `181b2383..be50ae3a`, the code read whole (API, web types, page,
   UI test) and the guide compared with the code by hand. Found F1.
2. External 1, Claude Code GitHub Action (request 2026-11-19T21:28:32Z): read the changed
   parts of `git_servers.py`, `git_entries.py`, `models.py`, `gitlab.py`, `GitServers.tsx`,
   the unit tests and part of the guide; not openspec, CHANGELOG, ui.md, install.md, the UI
   and vitest tests or the generated files, which the local round covered. Found F1 (merged
   with the local one), F2, F3, F4.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | the guide shows the glab ending only in Check's `Works: signed in as …` line, not in its first-check form, `✓ Saved:` or `✓ Token replaced:`, though step 1 announces and quotes it | declined: the ending's meaning and words are in the guide; a cheap fix if the human wants it |
| F2 | minor | the quote test's fragments for `Works: <Kind>, signed in as` and `Saved: …` are short, so rewording only those lines would not fail it | declined: an f-string yields only pieces; the lines' behaviour is pinned by unit, vitest and UI tests |
| F3 | — | the guide test imports `anchors` from another test module | refuted: tasks.md 4.1 asks for it; a rename fails loudly |
| F4 | — | the ending is not repeated in the closed server row | refuted: out of scope by the design |

## Metrics

- Rounds: 1 local, 1 external, 0 stand-ins.
- Confirmed: local 1 (minor), external 2 (minor, one merged with the local one).
- Refuted: external 2.
- Findings in code changed by the developer's cleanup: 0.

## Checks

- At `be50ae3a`: `make lint` clean; `tests/test_git_servers_guide.py`,
  `tests/test_git_servers.py`, `tests/test_server_git_servers.py` 403 passed;
  `openspec validate git-servers-guide --strict` valid; trial archive, 87 passed.
- CI of PR #345 at `be50ae3a`: 27/27, `ci-ok` green.

## Found on the way

- Nothing.

## Residual risk

- The certificate command in Docker (`docker compose exec -T lado lado git-server
  certificate <address> - < <file>`) was not run in a container; the code reads `-` from
  stdin and `exec -T` passes stdin.
- `make test`, `make web` and the UI test ran in CI only, on the same head.
- The guide's clarity for a reader who is not an engineer is the human's manual check,
  steps in the pull request's description.
