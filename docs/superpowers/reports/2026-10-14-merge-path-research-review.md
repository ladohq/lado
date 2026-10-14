# LAD-58 merge-path-research: review report

Pull request #39 `fix/lad-58-merge-path-research` → `main`. Scale: tweak, no version bump
(a research report and its measurement script under `docs/research/`, no product code),
review depth precision. Head reviewed last: `931d0e1` (= the remote head); the archive
commit follows it. No API, MCP, CLI or schema change, no CHANGELOG.md line.
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
are untouched: no live tests needed before the merge.

## Rounds

- **Round 1** (`b6babcf..866ac20`, local, precision): the diff read against the spec
  (AC-1-AC-8, D1-D5, tasks.md), the reviewer's own run of `measure.py`, section 2 checked
  against GitHub and `lado.db`. Found F1 (important), F2 and F3 (minor).
- **Round 2** (`866ac20..931d0e1`, local, precision on the delta): F1 and F2 fixed, nothing
  new. `make lint` exit 0, `openspec validate --strict` valid, `measure.py` exit 0.
- **External round 1 of 1** (Claude Code Action; request at 18:06:38 UTC, "Claude
  finished" at 18:07:40 UTC): no blocker, no important finding; 6 items, 2 refuted,
  4 minor declined. The external round cap for a tweak (1) is used.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | R3's path filter for smoke did not cover what smoke checks (`tmux.py`, `loop.py`, `state.py`, `gui_session.py`, `uv.lock`…), though macOS is checked in CI only by smoke; the promised guard test was not named | confirmed | important | fixed in `931d0e1`: the list now names the paths smoke is skipped for (`web/`, `docs/`, `openspec/`, `tests/ui/`, `tests/js/`, root Markdown, `.github/dependabot.yml`), with the guard test and the macOS risk; the reviewer's run gave the same 13 of 38 pull requests |
| F2 | 1 | local | design.md kept the docs-only skip that was not taken and its "5 of 38" | confirmed | minor | fixed in `931d0e1` |
| F3 | 1 | local | the commit author's e-mail shows the machine's name | confirmed | minor | declined: every commit of `main` is signed so; the human's call |
| E1 | 2 | external | R3's mechanism unnamed: `paths-ignore` on the whole workflow would skip `ci-ok` and leave the pull request waiting | refuted | — | only `ci-ok` is required (R2) and smoke is not; how to filter (at job level) goes to LAD-60 |
| E2 | 2 | external | a daily smoke by `schedule` in `ci.yml` runs the whole CI daily; a separate workflow needs its matrix checked against `PINS` | confirmed | minor | declined: an implementation choice for LAD-60 |
| E3 | 2 | external | R4's `concurrency` group puts a `schedule` or `workflow_dispatch` run in one group with the push run of the same commit | confirmed | minor | declined: it only waits; `github.run_id` for non-PR events goes to LAD-60 |
| E4 | 2 | external | `ci-ok` needs `if: always()`, else it is skipped when a job fails or is cancelled | confirmed | minor | declined: an implementation detail for LAD-60, to pin in its guard test |
| E5 | 2 | external | `measure.py` cuts its cache key to 200 characters | confirmed | minor | declined: keys are ~100 characters now, the cache only with `--cache` |
| E6 | 2 | external | `immutable=1` on a live WAL `lado.db` can read inconsistently; `--help` should say "copy" | refuted | — | `--help` already says "a copy of lado.db, opened read-only" |

| Source | Confirmed | Refuted |
|---|---|---|
| local | 3 (F1, F2, F3) | 0 |
| external, Claude Code Action | 4 (E2-E5) | 2 (E1, E6) |

## Not checked (residual risk)

- LAD-60's text in the tracker after the F1 fix: taken from the developer's word.
- The links of section 4 were not opened by the reviewer (the developer reports all
  answered 200, one 202).
- No tests run locally: only documents and a script outside the package changed; CI ran
  everything and is green (12/12 on `931d0e1`).

## Found on the way

None.
