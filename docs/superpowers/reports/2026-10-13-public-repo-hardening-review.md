# LAD-39 public-repo-hardening: review report

Pull request #18 `fix/lad-39-protect-public-repo` → `main`. Scale: tweak, review depth:
precision. Head reviewed last: `26c5885`; the archive commit follows it. Repository files
only: `.github/workflows/{ci,claude,release,windows-shell}.yml`, `.github/dependabot.yml`,
`SECURITY.md`, `docs/design/macos-gui-session.md`, AGENTS.md and the workflow tests;
nothing in `src/` or `web/`, no provider code, no schema migration, no MCP change.

## Rounds

- **Round 1** (`2440f02..5934a18`): local precision pass and a check against the change's
  spec, then external round 1 by the Claude Code Action (request comment 6144665334,
  "Claude finished … in 26s" in 6144669365): no confirmed finding. CI red on main's own
  failures on 0.37.0rc1 and a flake; the human chose `changes`: wait for #17, merge main,
  fix F1 and F2, get CI green, no merge around the ruleset.
- **Round 2** (`5934a18..26c5885`): precision pass over the delta (the merge of main with
  #17, `6f379d9`, `26c5885`), no external round (the human's decision). F1 and F2
  resolved, no new finding. External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local: precision | SECURITY.md mixed voices ("The maintainers aim to answer…", then "we will tell you…") | confirmed | minor | fixed in `6f379d9`: "the maintainers" throughout |
| F2 | 1 | local: PR description | "How it was checked" named only two `test_doctor` failures, while CI was also red on `ui` and a codex/macOS flake (run 38391058624) | confirmed | minor | fixed: the description rewritten (make test 2786/0, the ui flake on `d6865fd`, CI green on `26c5885`) |
| E1 | 1 | external (Action) | `issues: assigned` checks the issue's author, not who assigned it | refuted | — | as the spec says ("whose author…"), and the safe side (`claude.yml:8-9`) |
| E2 | 1 | external (Action) | A MEMBER's review on a fork's pull request gets no secrets | refuted | — | GitHub's handling of forks, the same before this change |
| E3 | 1 | external (Action) | dependabot.yml's validity shows only after the merge | unverifiable | — | residual risk: task 4.1, Insights → Dependency graph → Dependabot |
| E4 | 1 | external (Action) | The pin test does not cover `uses:` outside `.github/workflows` | refuted | — | no `action.yml` / `action.yaml` in the repository (node_modules and .venv aside) |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 2 (F1, F2; both minor, fixed) | 0 | 0 |
| external, Claude Code Action | 0 | 3 (E1, E2, E4) | 1 (E3) |

No blocker and no important finding.

## Found on the way

- A UI flake: `tests/ui/test_chat.py::test_a_workers_question_with_the_supervisors_recommendation_open_and_closed`
  failed in CI on `d6865fd` (run 38394892190, job `ui`, first attempt: the text "Later: CI
  is red on the branch." not found) and passed on the rerun; the pull request touches
  neither `web/` nor `tests/ui/`. Not in BACKLOG.md; proposed as P2, the human decides.

## Checks

- CI on `26c5885` (run 38396067760): 12 of 12 jobs green, first attempt.
- Local: `tests/test_workflow_security.py` 12 passed; by the developer's report `make
  test` 2786 passed, 0 failed, `make lint` clean, `openspec validate` valid.
- Each SHA pin checked by hand against its tag.
- Not run: integration, UI and smoke locally (no code change; green in CI); live tests
  (not needed: `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py`,
  `tests/live/` untouched).

## Residual risk

- Dependabot's config (`cooldown`, groups, the `uv` ecosystem) can only be seen accepted
  after the merge (E3, task 4.1).
- Until "Require actions pinned to a full-length commit SHA" is switched on (task 4.1),
  only `tests/test_workflow_security.py` holds the pins.
- `release.yml` (setup-uv v10.3.0 and checkout v7.0.1 pinned, with `id-token: write`) and
  `windows-shell.yml` first run their new pins on the next tag and the next Windows probe;
  the same pins already ran green in `ci.yml`.
- `claude.yml`'s guard acts only from `main`: GitHub takes an `issue_comment` workflow from
  the default branch.
