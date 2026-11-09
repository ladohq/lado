# LAD-248 ci-faster-ui-and-container: review report

Pull request #263 `fix/lad-248-ci-speedup` → `main`. Scale: tweak. Head reviewed: `41cbfa31`.
CI only: every job of `ci.yml` gets `timeout-minutes`; the UI tests run in four shards that
build only the bundle, `make dist` and the Node tests move to a new job `web` (the job `js`
goes); the UI jobs take Chromium and the `--with-deps` packages from a GitHub cache saved by
runs outside pull requests; the container tests run in two shards per architecture
(`scripts/smoke_ci.py container <out> [K/N]`). Delta: changes to `continuous-integration`.

## Rounds

1. Local, precision, `a3e4f80c..41cbfa31`, with the change's delta read whole: every
   requirement and scenario covered by code and tests, tasks 1.1-5.2 checked, D1-D7 kept,
   nothing out of scope touched (no `docker/Dockerfile`, no buildx cache). Found F1.
2. External 1, Claude Code GitHub Action (run 42603203658): E1-E5. Requested at 10:19:41Z,
   started by GitHub only at 10:44:13Z, at the edge of the 25-minute ceiling; the answer was
   waited for. It read `ci.yml`, `scripts/smoke_ci.py`, `tests/test_ci_workflow.py`,
   `tests/test_workflow_security.py` (every risky file), not the docs, openspec or
   `tests/test_smoke_ci.py`, which the local round read.

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- Scale tweak agreed at the design (#5039); the line "What CI proves" of `.lado/sdlc.md`
  changed with the human's consent.
- The before/after median over ~20 runs is the supervisor's, after the merge.
- **Gate `merge_ok`, approved** with no comment: F1 and E4 stay declined.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | The docstring of `tests/test_ci_workflow.py:3-4` is broken grammatically | declined: the loop converged before a next edit; may be fixed on the way |
| E1 | — | external: no fallback when `dpkg -i` fails on a hit | refuted: a cache that does not install fails loudly by design (D4); the key holds the image version |
| E2 | — | external: a miss copies every `.deb` of `/var/cache/apt/archives`, not only the new ones | refuted: on the image the folder holds only the nine fonts `--with-deps` downloaded (dispatch 42597082362) |
| E3 | — | external: `split("else\n")` in the test breaks silently | refuted: the unpacking `hit, miss = ...` raises `ValueError` |
| E4 | minor | external: the container shards are uneven (28 and 36 tests) | declined: the split is `tests/shard.py`'s shared CRC-32, out of scope; cells take 4.5-5.5 min |
| E5 | — | external: `good_shard` accepts `01/2` and Unicode digits | refuted: the same pattern and check as `tests/shard.py:14-23` |

## Checks

| Check | Head | Result |
|---|---|---|
| CI of the pull request, required `ci-ok` | `41cbfa31` | green (run 42599605809); ui (1)-(4) 6.3, 6.6, 4.8, 4.9 min; container cells 4.5-5.5 min; web 2.5 min |
| Browser cache, `workflow_dispatch` on the branch | `d45c3335` | run 42597082362: `ui (2)` missed and saved; `ui (1)`, `(3)`, `(4)` hit in 4-8 s, no `Get:` line, no `apt-get update` |
| `make lint` | `41cbfa31` | clean |
| `make test` | `41cbfa31` | 6054 passed, 7 skipped |
| `openspec validate ci-faster-ui-and-container --strict`; `--specs --strict` and the trial archive | `41cbfa31` | valid; 82 passed |
| `openspec validate --specs --strict` after the archive | archive commit | 82 passed |

AC-3 asked for two dispatch runs; one run showed both the miss and the hit in different
shards, accepted by the reviewer. The live tests were not run: `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change.

## Residual risk

- The first push to `main` after the merge: four UI shards miss at once and save one key;
  one saves, the others should only warn. Not seen live.
- Pull requests hit the cache only once `main` saved it (a dispatch's entry is in the
  branch's scope); the scenario "a pull request after main" has not run yet.
- LAD-249 changes the job `container` too: whichever merges second resolves the conflict;
  the Docker layer cache is best written by one cell per architecture (e.g. shard 1).

## Found on the way

- `scripts/smoke_ci.py` repeats `tests/shard.py`'s parsing of `K/N`, so a bad shard is
  refused before pytest starts. No defect.
