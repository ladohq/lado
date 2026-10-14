# LAD-60 ci-shards-and-ci-ok: review report

Pull request #44 `fix/lad-60-ci-shards-ci-ok` → `main`. Scale: tweak, no version bump and
no CHANGELOG line (only CI changes). Review depth: precision, widened to the whole diff,
as `.github/workflows/ci.yml` and the ruleset of `main` are the risky part. Head reviewed
last: `1e93586` (= the remote head); the archive commit follows it. `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` are
untouched, so no live tests were needed.

## Rounds

- **Round 1** (local, `origin/main...1e93586`): the spec `continuous-integration` against
  the code and tests, tasks.md, D1-D8, scope, `ci-ok`'s fail-safety (a failed `changes`
  reads as smoke needed, so a skipped smoke fails `ci-ok`), the `changes` step's inputs
  (the SHAs through env, never in the script), `base...head` with `--no-renames`, the
  skip list's guard. F1 and F2 (minor) found.
- **External round 1** (Claude Code Action, `@claude review`): request comment
  6176310604 at 19:14:50Z, "Claude finished" at 19:16:08Z. No blocker; two remarks, both
  refuted (E1, E2). 1 of 1 external rounds used.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | proposal.md, design.md D1 and tasks.md 1.2 put `--shard` in `tests/conftest.py`; it lives in `tests/shard.py`, which conftest imports | confirmed | minor | declined: only the change's text differs; the code, AGENTS.md and the pull request's description are right |
| F2 | 1 | local | conftest imports `pytest_configure` and the other hooks from `shard`; a `pytest_configure` of conftest's own would silently replace it | confirmed (a future risk) | minor | declined: no such hook in `tests/` today (grep); the comment in conftest names `tests/shard.py` |
| E1 | ext 1 | external | `ci_ok.py` comes from the pull request's own checkout, so a pull request can change its own verdict | refuted | — | ci.yml is under the pull request's control anyway; no new trust boundary |
| E2 | ext 1 | external | nothing guards that the shards together hold every test; a parametrized test with an unstable id could land in 0 or 2 shards | refuted as a defect; the guard test is a minor suggestion | minor | declined: two separate collections gave the same 255 node ids; the shards add up (45+38+52=135, 60+60=120); xdist fails on differing collections in `ui` |

Found on the way: nothing.

## Checks

- `make lint`: exit 0. `make test`: 3082 passed.
- `openspec validate --specs --strict` and `openspec validate ci-shards-and-ci-ok
  --strict`: valid.
- Local collection per shard: integration 45 + 38 + 52 = 135, UI 60 + 60 = 120, all.
- CI on `1e93586` (run 38621585188): all 21 jobs and `ci-ok` green, about 3.4 minutes
  (19:11:38 → 19:14:59); the smoke ran, as the pull request changes `scripts/`. The
  slowest shard: `integration (3.10, 3)`, 52 tests, 3:03.

## Not checked / residual risk

- `make test-integration` and the UI tests were not run whole locally; CI ran them in
  shards on this head. The smoke ran only in CI.
- Not yet seen live: the smoke skipped on a documentation-only pull request (unit tests
  and a local `smoke_ci.py needed` cover it), a pull request's older run cancelled, the
  daily `schedule`.
- The hash does not balance the shards by time.

## At merge

Task 5.3 (D8) is the integrator's, after this report: the ruleset "main: PR and green CI"
required `check (3.10)`, `check (3.13)`, `js` and `ui`, which this workflow no longer
reports; with the human's yes at `merge_ok` it is switched to `ci-ok` only, the pull
request merged, and `ci-ok` checked green on `main`.

Verdict: converged.
