# LAD-312 commit-author-levels: review report

Pull request #357 `feature/lad-312-commit-authors` → `main`. Scale: full. Head reviewed:
`1e093118`. Commits get their author from one order: the project's author, then the git
server's, then LADO's own author (Settings → Git servers), then the human's own git config;
`GIT_AUTHOR_*` in the environment win over all. LADO's and the project's authors live in
lado.db; agents get them as git config entries through variables, as the server's author
before. LADO itself (a new project's first commit, the New session check) follows the same
order.

## Rounds

1. Local, breadth, `origin/main...cabda3c3`: a manual read of the core and two helper
   lenses (UI; spec and tests). 2 blocker, 6 important, 7 minor (4 of them to fix).
2. Local, precision, `cabda3c3..1e093118` (9 commits, 22 files): no new findings; the
   MODIFIED deltas of `projects` checked against the living requirements, scenarios kept.
   External 1, Claude Code GitHub Action (request #issuecomment-7127005029, answer
   #issuecomment-7127010343, reply #issuecomment-7127062153): 6 findings, 4 refuted, 2
   minor declined. The external reviewer read the Python of the core, the server and the
   entrypoint, not `src/lado/server/models.py`, `docker/compose.yaml`, tests, web, docs or
   openspec; round 1 covered those locally.

External rounds used: 1 of 2.

## Findings

| ID | Finding | Level | Outcome |
|---|---|---|---|
| F1 | The update test took the previous schema (`SCHEMA_VERSION - 1`) for one without `github_takeover` | blocker | fixed in `16132487`: pinned to schema 42 (`agent_helpers.schema_before(43)`) |
| F2 | The `Set author` button 32 px high on a phone instead of 44 | blocker | fixed in `e48bd604` |
| F3 | After a git server's removal LADO's author block showed "Nobody" | important | fixed in `fa544d67`: the removal answers the full listing |
| F4 | `lado git-server author` traced back on an unreadable git config | important | fixed in `f3c7c4c8`: one line, exit 1 |
| F5 | `lado project show` contradicted the living spec `projects` | important | fixed in `ac16612f`: an `author:` line after `made:`, MODIFIED deltas |
| F6 | The delta forbade agents `lado project author` whole, the code only its change | important | fixed in `ac16612f`, `ecfae408` |
| F7 | A project's author line led with the author of most repositories | important | fixed in `fb146249`: leads with `project.commit_author` |
| F8 | `setup.make`'s refusal without an author came without a hint | important | fixed in `1ee5d79d`; the 400 of `POST /api/sessions` still carries only the text, as other start refusals |
| F9–F12 | Stale `docs/git-servers.md`, `docs/design/modules.md`, the doctor delta, `tasks.md` 8.2/8.3 | minor | fixed in `ecfae408` |
| F13 | New session does not reset the author it found | minor | declined: no silent loss, the server refuses the start |
| F14 | "Go back to the New session tab" stays after the first save | minor | declined: cosmetic |
| F15 | The pre-check counts the project by path, `make` does not pass it | minor | declined: unreachable, `in_project` refuses first |
| E1 | `launch.author_variables` runs a login shell on each read of a project and of Git servers | minor | declined: chosen in design D5, reads are async; a short cache is a cheap follow-up |
| E2 | Source `SERVER` for a new repository's first commit | — | refuted: `scratch._check_target` refuses `inside_repo` first |
| E3 | `in_effect` computed twice in `scratch.make`/`setup.make` | minor | declined: extra git runs only |
| E4 | `set_lado`/`set_project` check git on LADO's PATH | — | refuted: design D6; the start checks the agents' PATH |
| E5 | `ALTER TABLE` fails on a repeated partial migration | — | refuted: one `BEGIN IMMEDIATE` transaction |
| E6 | doctor's `git author` OK with git < 2.31 | — | refuted: the `git` check above warns |

Metrics: 2 local rounds, 1 external, 0 substitute; 15 local findings confirmed, 0 refuted;
2 external confirmed, 4 refuted; 0 findings in code changed by the developer's clean-up.

## Checks at `1e093118`

- `make lint`: clean
- `make test`: 6204 passed, 14 skipped
- `pytest -m integration` on `test_update_process.py` and `test_commit_author_order.py`:
  17 passed
- `openspec validate commit-author-levels --strict`: ok; `openspec validate --specs
  --strict`: 90 passed; trial archive: 91 passed
- CI: 27/27 pass, `mergeStateStatus: CLEAN`

## Not checked, residual risk

- Live tests (`make test-live`) not run; the change touches `runtime.py`
  (`_check_commands`, `_ours`, `_git_server_warnings`).
- UI e2e and `make web` not rerun locally in round 2; CI covers them.
- The external reviewer is the same model family and did not read `models.py` or
  `compose.yaml`.
- E1: the cost of a login shell per page read depends on the human's rc files.

Found on the way: none.
