# LAD-140 unpushed-skips-links: review report

Pull request #163 `hotfix/lad-140-unpushed-skips-links` → `main`. Scale: hotfix, reviewed
for precision. Head reviewed last: `a447bb6f` (= the remote head), base `8eeb850a`. The
change is one filter in `projects.unpushed` (`src/lado/projects.py`), its unit tests,
`docs/design/projects.md` and the spec delta; `providers/`, `hooks.py`, `mcp_server.py`,
`runtime.py`, `agent_env.py` and `tests/live/` unchanged, so no live tests are needed
before the merge. Schema migration: no.

## Rounds

- **Round 1** (`origin/main..0f6d8797`, the whole pull request): a local precision pass
  with the check against the change's spec, a mutation of D1 and edge-case probes, and
  **external 1** (Claude Code GitHub Action, requested 06:24:55Z, finished 06:25:42Z):
  E1, E2. The external reviewer read `src/lado/projects.py`, both test files and
  `docs/design/projects.md`; not the openspec change's files (read locally).
- **Round 2** (`0f6d8797..a447bb6f`): a return after `merge_ok`, as the archive failed
  `openspec validate --specs --strict` (a requirement over 500 characters). The link rule
  moved to a requirement of its own; a precision pass over the spec delta and a trial
  archive in a copy of `openspec/`. No external round: the hotfix cap (1 of 1) was used
  and the code did not change.

External rounds used: 1 of 1. The external reviewer is of the same model family, so its
"nothing blocking" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | `tasks.md` 1.2 says the AC-3 test holds before and after the fix, but it fails on `main` (the link had a line of its own there) | confirmed | minor | fixed in `a447bb6f` (declined in round 1, fixed with the spec's rework) |
| E1 | 1 | external 1 | the comment at `skip` ("links to one") is true only because `repos` holds links; a later cleanup could break AC-3 | refuted | — | the comment matches the code; the mutation dropping links from `skip` fails `test_a_link_in_a_clean_root_is_not_the_roots_change` |
| E2 | 1 | external 1 | a link to a non-repository in a root repository counts as the root's change | refuted | — | unchanged behaviour, by design (D1 is about links to a repository) |

## Checked against the spec

AC-1 to AC-4 hold, each scenario covered by a test:
`test_a_link_to_a_repository_is_not_scanned`, `test_a_repository_beside_a_link_is_still_named`,
`test_a_worktree_of_the_links_repository_has_a_line_of_its_own`,
`test_a_link_in_a_clean_root_is_not_the_roots_change`. D1 guarded by the AC-3 test
(mutation red); D2-D5 kept; nothing out of scope. Round 2: the delete requirement of the
living spec stays unchanged, the new requirement "The unpushed check does not scan a link
in a project's folder" carries the link rule and both its scenarios word for word.

## Checks

Round 1: `make lint` 0; `make test` 4239 passed, 2 skipped; the 4 new tests fail on
`projects.py` from `main`; `openspec validate unpushed-skips-links --strict` valid.
Round 2: the change valid; the trial archive then `openspec validate --specs --strict` 47
passed, 0 failed; CI on `a447bb6f` 23 of 23 success, `ci-ok` and smoke included.

## Not checked

The integration, UI and smoke tests locally (their files unchanged; green in CI). The
spec's new layout was read only by the local pass and the trial archive, not externally.
