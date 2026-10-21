# LAD-117 workspace-name-and-projects-docs: review report

Pull request #126 `fix/lad-117-workspace-docs` → `main`. Scale: tweak, reviewed by
precision, widened in round 1 to the lenses spec, tests, comments and general, as the diff
rewrites contract documents (`docs/design/projects.md`, ROADMAP, BACKLOG,
`docs/design/ui.md`) and visible texts. No behaviour changes, so the silent-failure and
types lenses were skipped. Head reviewed last: `312ca12` (= the remote head). In
`runtime.py` only a text constant and a docstring changed; `providers/`, `hooks.py`,
`mcp_server.py`, `agent_env.py` and `tests/live/` did not change.

## Rounds

- **Round 1, local** (wide, `f044020..9d4fdff`, 41 files): `projects.md` read against the
  concept and the code, screenshots against `ui.md`. F1, F2.
- **Round 1, external** (Claude Code GitHub Action; request comment 6314440102, answer
  6314444350): no blockers; E1 refuted, E2 minor. It is of the same model family, so its
  "nothing more" weighs less.
- **Merge gate:** the human sent the change back so that F1 is fixed in this pull request.
- **Round 2, local** (precision over `9d4fdff..312ca12`, 5 files): F1 resolved, the ssh
  requirement's REMOVED + ADDED checked line by line against the living spec. No new
  findings.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (comments) | "projects" in the old sense (the workspace) left in `README.md`, three `docker/Dockerfile` comments, two container test docstrings and the ssh requirement of the `container` spec | confirmed | minor | fixed in `312ca12` at the human's word at the merge gate (was declined); the ssh requirement renamed by REMOVED + ADDED |
| F2 | 1 | local (tests) | the Projects placeholder's new sentence (`web/src/pages.tsx`) is checked by no test | confirmed | minor | declined: a text step adds no tests (design, decision 8); the human left it at the gate |
| E1 | 1 | external | `lado doctor` should show which workspace is in effect, yet prints no line without `LADO_REPOS` | refuted: until S2 there is no workspace without `LADO_REPOS` | — | dropped |
| E2 | 1 | external | scripts that grep `Repositories folder` in `lado doctor`'s output break | confirmed | minor | declined: the label is text, not a machine interface, and CHANGELOG names the new label; the human left it at the gate |

Metrics: 2 local rounds, 1 external, 0 substitutes. Local confirmed 2 (F1, F2), refuted
0; external confirmed 1 (E2), refuted 1 (E1). Findings in code changed by the
developer's cleanup: 0.

## Checks

- `grep -rniE "projects folders?|repositories folders?"` outside the historical documents:
  0 after the archive.
- `openspec validate --specs --strict`: 42 of 42 after the archive.
- `make lint` green; CI 23 of 23 on `312ca12`, the container tests included. The developer
  reported `make test`: 3614 passed.

## Not checked

- `docs/design/projects.md` against the concept (AC-1) is the human's at the merge gate;
  the reviewer read it whole and found no difference of substance.
- `make test`, `make web` and the UI test were not rerun locally in round 2, whose delta
  does not touch them; CI ran them on `312ca12`.
