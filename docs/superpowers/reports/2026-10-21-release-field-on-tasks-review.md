# LAD-119 release-field-on-tasks: review report

Pull request #132 `fix/lad-119-release-field` → `main`. Scale: tweak, reviewed by
precision: the diff touches `.lado/sdlc.md`, `.lado/tracker.yaml`, `docs/release.md` and
the openspec change, no code, so no breadth pass. Head reviewed: `8d19332` (= the remote
head). `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` did not change, so no live tests were needed.

## Rounds

- **Round 1, local** (precision, `a4762ec..8d19332`, all 6 files): the diff against the
  `release-tracking` delta and `tasks.md`, the section After the merge against kit-sdlc's
  `sdlc.example.md`, the `fields:` format against the tracker-yougile skill, and a grep of
  the repository for the old merge rules ("Waiting for release label", "as **Tracker**
  says"): none left, no contradicting rule in `openspec/specs/`. No findings.
- **Round 1, external** (Claude Code GitHub Action; request 19:55:33Z, comment
  6325196615, "Claude finished" after it): no blockers; E1, E2 confirmed, E3, E4
  refuted. It is of the same model family, so its "nothing more" weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| E1 | 1 | external | `docs/release.md` says "unchanged when it already holds it", the `release-tracking` requirement does not | confirmed | minor | declined: setting X.Y.Z over X.Y.Z is that "unchanged"; a refinement, not a contradiction |
| E2 | 1 | external | the epic part "Post the comment above with the first line …" relies on the rest of the template staying | confirmed | minor | declined: it reads unambiguously as the same template with its first line replaced, as kit-sdlc's `sdlc.example.md` words it |
| E3 | 1 | external | a merge without an `(unreleased)` heading leaves an older `release` value on a task that had one | refuted: by design (AC-2), and the final release corrects it | — | dropped |
| E4 | 1 | external | task 3.3 is open | refuted: by design the integrator does it after the merge | — | dropped |

Metrics: 1 local round, 1 external, 0 substitutes. Confirmed 2 (external), both minor,
both declined; refuted 2 (external). Findings in code changed by the developer's cleanup:
0.

## Checks

- Head `8d19332`: `make lint` green; `openspec validate release-field-on-tasks --strict`
  valid; `openspec validate --specs --strict` 43 of 43; `tests/test_agents_md.py` 3
  passed. `make test` (developer): 3615 passed, 1 skipped.
- CI on `8d19332`: 23 of 23 green, `ci-ok` included (unit 3.10/3.13, integration, js,
  ui, container, smoke ubuntu/macOS × 4 providers).
- At archive: the new capability's Purpose written in place of openspec's placeholder;
  `openspec validate --specs --strict` 44 of 44.

## Not checked

- The section's effect in the tracker shows only at this pull request's merge (task 3.3,
  the integrator's note).
- The final release's step 3 (`docs/release.md`) runs only at the next final release.

## Found on the way

None.
