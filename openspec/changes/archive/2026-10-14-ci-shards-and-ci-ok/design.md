## Context

`.github/workflows/ci.yml` has four jobs: `check` (per Python: ruff, the unit tests
`-n auto`, then the integration tests `-n0`), `js`, `ui` (`make dist`, Chromium, the UI
tests `-n 2`) and `smoke` (per system and provider). Its critical path is `check`: the
integration step is 6 min (docs/research/merge-path.md, 3.2). The ruleset "main: PR and
green CI" requires `check (3.10)`, `check (3.13)`, `js` and `ui`.
`tests/test_ci_workflow.py` pins the pytest commands and the smoke's matrix.

Root cause of the wait: one process runs all 135 integration tests serially on each
Python, after the unit tests in the same job; and every pull request waits for 8 smoke
runners, 4 of them macOS with a queue p90 of 3-5 min, whatever it changes.

Options weighed for the shards:
1. A static list of test files per shard in ci.yml: balanced by hand, but every new test
   file needs an edit and a guard test; the list drifts from the measured times.
2. A stable hash of each test's node id (`--shard K/N`, chosen): no list to keep, a new
   test lands in a known shard, ~45 tests per shard balance statistically; costs one
   small conftest hook.
3. pytest-split or pytest-shard: a dependency for ten lines of code; pytest-split also
   needs a committed durations file to stay balanced.

Options weighed for the smoke filter:
1. `paths-ignore` on the workflow: refused (E1): the whole run, `ci-ok` too, would not
   report, and the pull request would wait for a required check forever.
2. A third-party paths-filter action: one more pinned action that reads the list in its
   own syntax.
3. A job `changes` that runs `scripts/smoke_ci.py needed` on `git diff` (chosen): the
   list stays in ci.yml, the logic is standard-library Python with unit tests.

## Decisions

- **D1. Shards by a stable hash of the node id.** `tests/conftest.py` adds `--shard K/N`
  (1 <= K <= N); `pytest_collection_modifyitems` keeps an item when
  `zlib.crc32(item.nodeid) % N == K - 1` and reports the rest as deselected. Node ids
  rather than files: `tests/integration/test_agents.py` alone holds a fifth of the
  integration tests, so a file split leaves one shard much slower; no fixture of these
  layers has a module or package scope, so splitting a file costs nothing. Without the
  option nothing changes. A bad value is a usage error (`pytest.UsageError`).
- **D2. Job names.** `unit (3.10)`, `unit (3.13)`; `integration (3.10, 1)` …
  `integration (3.13, 3)` (matrix `python-version` × `shard`); `ui (1)`, `ui (2)`; `js`;
  `changes`; `smoke <os> <provider>` as now; `ci-ok`. The ruleset names only `ci-ok`, so
  later reshaping touches no setting.
- **D3. The second UI shard builds only the bundle.** `make dist` (npm ci, stale types,
  tsc, vitest, build, sdist and wheel checks) stays in `ui (1)`; `ui (2)` runs
  `cd web && npm ci --no-audit --no-fund && npm run build`, which is what the UI tests
  need (`src/lado/server/static`), so the web checks run once.
- **D4. The smoke question: job `changes`.** It checks out with full history and runs
  `python3 scripts/smoke_ci.py needed` with the event's name and, on a pull request,
  `github.event.pull_request.base.sha` and `.head.sha`; it writes `smoke=true|false` to
  `$GITHUB_OUTPUT`. Outside a pull request the answer is `true` without a diff. On a pull
  request it takes `git diff --name-only <base>...<head>`; the answer is `false` only when
  that list is not empty and every file is on the skip list (an entry ending in `/` is a
  folder prefix, another an exact path). The skip list is an env value of that step in
  ci.yml, one path per line, so the list is written once, where a reviewer of ci.yml sees
  it; the script reads it from the environment and refuses an empty one. The job `smoke`
  has `needs: changes` and `if: needs.changes.outputs.smoke == 'true'`.
- **D5. ci-ok's verdict in a script.** `ci-ok` runs `python3 scripts/ci_ok.py` (standard
  library, no `uv sync`) with `NEEDS: ${{ toJSON(needs) }}`. It prints one line per job
  with its result and fails when any is not `success`, except `smoke` `skipped` while
  `changes`' output `smoke` is `false`. A `cancelled` job fails it. The script is unit
  tested; `tests/test_ci_workflow.py` checks that `ci-ok`'s `needs` is every other job
  and its `if` is `always()` (E4).
- **D6. Daily and manual runs in ci.yml.** `schedule: cron '47 3 * * *'` and
  `workflow_dispatch` start the whole CI on `main`; the smoke comes with it. GitHub mails
  a red scheduled run to whoever last changed its cron line; no other channel (E2, the
  human's decision).
- **D7. Concurrency.** `group: ci-${{ github.event_name == 'pull_request' &&
  github.event.pull_request.number || github.run_id }}`, `cancel-in-progress: ${{
  github.event_name == 'pull_request' }}` (R4, E3): a pull request's newer run cancels
  its older one; a push, schedule or dispatch run is alone in its group.
- **D8. The ruleset switch.** The integrator, at `merge`, with the human's yes at
  `merge_ok`, sets the ruleset's required checks to `ci-ok` only (`gh api` on ruleset
  "main: PR and green CI") once `ci-ok` is green on this pull request, merges, and checks
  that `ci-ok` is green on `main`. Other open pull requests get `ci-ok` on their next push.

## Risks

- A shard much slower than the others: the hash is not balanced by time. The week's
  measurement shows it; a new seed or N is a one-line change.
- A wrong path on the skip list skips the smoke for a change it concerns: the guard test
  refuses the paths the smoke runs.
- `ci-ok` passing over a failure: its verdict is explicit per job and unit tested; `if:
  always()` is pinned by a test.
- During the switch, open pull requests started before it lack `ci-ok` until their next
  push.
