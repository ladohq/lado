## 1. Time limits

- [x] 1.1 `timeout-minutes` on every job of `ci.yml` by design D1; a unit test in
  `tests/test_ci_workflow.py` that every job sets one (scenario "A job without a limit").
  Check: `make test`.

## 2. The UI in four shards and the job web

- [x] 2.1 `ui`: matrix `shard: [1, 2, 3, 4]`, `--shard ${{ matrix.shard }}/4`, the bundle
  step without a condition, no `make dist` (D2). Job `web`: uv, Node with the npm cache,
  `uv sync --locked`, `make dist`, `node --test tests/js/*.test.mjs`; job `js` removed;
  `ci-ok.needs` updated (D3). Check: `tests/test_ci_workflow.py` pins both jobs' commands
  and shards; `make test`.

## 3. The browser from the cache

- [x] 3.1 The UI job's Playwright version step, cache restore, install (hit and miss
  branches), the apt settings file and the save on non-pull-request runs (D4). Check:
  `tests/test_ci_workflow.py` pins the key's parts, the save's condition and that no
  `--with-deps` runs on a hit; `make test`.

## 4. Container shards

- [x] 4.1 `scripts/smoke_ci.py container <out> [K/N]` adds `--shard K/N` and keeps the pass
  rule; usage and docstring. Check: `tests/test_smoke_ci.py`: with a shard the command ends
  in `--shard 1/2`, without one it is today's, a bad shard is a usage error; `make test`.
- [x] 4.2 `container` matrix arch × shard, name, run line and artifact name (D5). Check:
  `tests/test_ci_workflow.py`; `make test`.

## 5. Docs and the checks

- [x] 5.1 `docs/testing.md` (CI paragraph: jobs, shards, `web`, the browser cache, time
  limits) and the line "What CI proves" of `.lado/sdlc.md`; `tests/test_ci_workflow.py`'s
  docstring. Check: `make lint`, `openspec validate ci-faster-ui-and-container --strict`.
- [x] 5.2 Push; the pull request's CI green; two `workflow_dispatch` runs on the branch:
  the first misses and saves the cache, the second hits (its browser step ≤ 15 s, no
  `apt-get update` in its log) (AC-3, D7). The build report lists each job's time against
  the baseline (AC-6).
