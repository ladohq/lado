# LAD-22 installed-kits-only: review report

Pull request #5 `feature/lad-22-installed-kits-only` → `main`. Scale: full, review depth:
breadth first. Head reviewed last: `9734afb`; the archive commit follows it. The kit
lookup loses its folder: a repository's `.lado/kits` is never read, `lado kits --repo` and
`GET /api/kits?where=` go, `runtime.kit_users` counts every session; tests install folder
kits with `tests/agent_helpers.install_kit`.

## Rounds

- **Round 1** (`origin/main..9734afb`): local breadth pass (spec, tests, silent failures,
  comments, general, and the architecture against AGENTS.md; types/invariants skipped, no
  new types), and the external round (1 of 2) by the Claude Code Action (request
  issuecomment-6119815182, "Claude finished" in issuecomment-6119818053). No blocker, no
  important finding: the loop converged after one round.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local: spec/tests; external | No test of the spec scenario "A stopped session whose kit was a project kit" (a resume fails with `kit "<name>" not found`) | confirmed | minor | declined: a resume takes the same `kits.resolve` path as a start, which unit and integration tests cover |
| F2 | 1 | local: comments | A search-and-replace left the test name `test_kits_check_warns_about_a_flow_role_of_another_installed` | confirmed | minor | declined |
| F3 | 1 | local: comments | An AGENTS.md line of the `launch.py` paragraph about `/api/kits` was not reflowed | confirmed | minor | declined |
| F4 | 1 | local: comments; external | BACKLOG.md still says "project kit" in the git cache cleanup entry | confirmed | minor | declined |
| E1 | 1 | external (Action) | `kit not found` gives no hint about an existing `<repo>/.lado/kits` | refuted | — | dropped: the task's decision (proposal, Out of scope; the spec says "nothing about project kits") |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 4 (F1–F4) | 0 | — |
| external, Claude Code Action | 0 new (confirmed F1, F4) | 1 (E1) | — |

No blocker, no important finding; the four minor ones were declined at convergence.

## Found on the way

- F4 (BACKLOG.md's git cache entry still names project kits): a one-line wording fix, no
  new entry.

## Checks

- On `9734afb`: `make lint` clean (189 files); `make test` 2351 passed; the changed
  integration files with `-m integration` 16 passed; the changed UI files with `-m ui` 48
  passed; `make web` stale-types ok, vitest 621 passed; `openspec validate --specs
  --strict` 2 passed and `openspec validate installed-kits-only --strict` valid; CI run
  38218097338 green (check 3.10/3.13, js, ui, 8 smoke cells).
- At archive: `openspec validate --specs --strict` 3 passed, 0 failed (the new capability
  `kit-lookup`).

## Residual risk

- `tests/live/test_live.py` was rewritten but not run (live tests run at release; Claude
  Code only with the human's yes). The change touches `runtime.py` and `tests/live/`.
- `make check`, `make test-integration` and `make test-smoke` were not run locally; CI ran
  them green.
- The new "a repository's kit is not read" tests were not seen red in a clean form (under
  the old signature they failed on a TypeError); read against the code, they catch the
  regression.
