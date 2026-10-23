# LAD-127 where-early-focus: review report

Pull request #142 `hotfix/lad-127-where-early-focus` → `main`. Scale: hotfix, reviewed
by precision. Head reviewed last: `db5d929` (= the remote head). Only the web UI (one
condition in `WhereField`'s `onFocus`), its unit tests, the spec delta and CHANGELOG.md
changed; `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` did not, so no live tests were needed.

## Rounds

- **Round 1, local** (`origin/main...31af919`, the whole pull request): the diff read by
  hand with the lenses spec, tests, general and comments. The fix `if (empty)
  setOpen(true)` is safe: while the workspace is unknown, `parent` is null and nothing
  is asked of the server. Every scenario of the delta has a test (AC-1, AC-2, AC-3).
- **Round 1, external** (Claude Code GitHub Action; request issuecomment-6348343369,
  "Claude finished" in comment 6348348950, newer than the request): no blockers, one nit
  (F2) and a claim that a rebase is needed (F3). It is of the same model family, so its
  "nothing more" weighs less.
- **Round 2, local** (`31af919..db5d929`, the spec delta only): a return from merge,
  where the archive's `openspec validate --specs --strict` failed: the modified
  requirement of `repos-folder` grew past openspec's 500 characters. Its first paragraph
  is now word for word the living spec; the early focus stays in the scenario "The focus
  before the server's answer". A trial archive in a scratch copy: 45 of 45 valid.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (spec) | `tasks.md` 1.2 says each new test fails without 1.1, which is not true of the guard tests AC-2 and AC-3 (they pass on the old code too); the build report says so | confirmed | minor | declined: wording only; the tests' ability to fail was shown by reverse probes |
| F2 | 1 | external | in `Launch.test.tsx` the local `withSlash` is declared after `holdWorkspace()`, which uses it | confirmed (style) | minor | declined: it is called only at run time; cosmetic |
| F3 | 1 | external | no merge base, `main` moved ahead (#141), a rebase is needed | refuted: the merge base `7788409` exists, the pull request was `MERGEABLE/CLEAN`, #141 meets it only in CHANGELOG.md without a conflict | — | dropped |

Metrics: 2 local rounds, 1 external, 0 substitutes. Local confirmed 1 (F1), refuted 0;
external confirmed 1 (F2), refuted 1 (F3). Findings in code changed by the developer's
cleanup: 0.

## Checks

- `make lint`: exit 0.
- `make web`: 53 files, 994 passed, the build ok.
- `uv run pytest -m ui tests/ui/test_launch.py -n auto`: 28 passed.
- `openspec validate where-early-focus --strict`: valid; `openspec validate --specs
  --strict`: 45 of 45 after the archive.
- CI on `db5d929`: run success, `ci-ok` green; the smoke skipped (every file of the diff
  on ci.yml's skip list).
- Not run locally: `make test`, the integration, smoke and live tests (no Python
  changed; CI green).

## Not checked

- AC-1 red before the fix, AC-4 by hand (the answer held back 1.5 s) and its 20 runs in
  a row rest on the developer's build report; the reviewer is read-only and confirmed
  them by the code's mechanism only.
