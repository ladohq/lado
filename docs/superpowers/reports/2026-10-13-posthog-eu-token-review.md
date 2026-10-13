# LAD-36 posthog-eu-token: review report

Pull request #15 `hotfix/lad-36-posthog-eu-token` → `main`. Scale: hotfix, review depth:
precision. Head reviewed last: `38dd46c`. LADO's telemetry token becomes the EU PostHog
project's (304141), and the Release workflow checks with `scripts/check_telemetry.py`
that the endpoint's region accepts it before it builds and publishes; no provider code,
no schema migration, no MCP or CLI change.

## Rounds

- **Round 1** (`origin/main...1c51321`): local precision pass. The script's tests 9
  passed, `make lint` clean, openspec valid, the real PostHog accepts the token (exit 0).
  CI had not run, as the PR conflicted with `main` (F1). Found F1–F4.
- **Round 2** (`1c51321..38dd46c`: the merge of `main` `abf2ffd` and the fixes
  `38dd46c`): local precision pass; `tests/test_check_telemetry.py` and
  `tests/test_release_workflow.py` 11 passed; CI 12/12 green on `38dd46c` (unit and
  integration on 3.10 and 3.13, js, ui, smoke ×8). No new findings.
- **External round 1** by the Claude Code Action (request 09:47:51 UTC, "Claude finished"
  09:48:56 UTC, `origin/main...38dd46c`): no blockers, two minor (F5, F6). It ran no code.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local: checks | The PR conflicted with `main` (release.yml, AGENTS.md after #13), so CI did not run | confirmed | blocker | fixed in `abf2ffd`: the telemetry step after `release_check.py`, both after the tag check and before `make dist` / `uv publish`; CI green on `38dd46c` |
| F2 | 1 | local: docs | `docs/release.md` did not name the token check | confirmed | important | fixed in `38dd46c`: section 6 has both lines and what to do, step 5.2 names it |
| F3 | 1 | local: tests | Tests of release.yml in two files | confirmed | minor | fixed in `38dd46c`: `test_the_telemetry_check_runs_after_the_version_check_and_before_the_build` in `tests/test_release_workflow.py` |
| F4 | 1 | local: correctness | A 301/302 redirect would turn the POST into a GET and the line would say "refuses" | confirmed (hypothetical) | minor | declined: PostHog does not redirect, and any non-2xx fails the release anyway, so no false green |
| F5 | ext 1 | external | `/flags/` accepts any valid token of the region, another project's too: the check proves the region, not the project | confirmed (as a property) | minor | declined: the design and the spec check the region, which is exactly this defect; the project (304141) is named in the comment and was checked by the human through the API |
| F6 | ext 1 | external | `docs/release.md:59-60`: uneven line wrapping | confirmed | minor | declined: cosmetic |

## Metrics

Rounds: 2 local, 1 external, 0 substitute. Findings: local 4 confirmed (1 blocker,
1 important, 2 minor), 0 refuted; external 2 confirmed (minor), 0 refuted. Findings in
code changed by the developer's cleanup pass: 0.

## Sensitive modules

`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py`, `tests/live/`:
not changed; no live tests needed before the merge.

## Not checked (residual risk)

- The Release workflow itself did not run: the step's place is pinned by a test, the
  script by its tests and by hand against the real PostHog. Its first real run is on the
  tag 0.37.0rc1.
- Delivery of events into project 304141 end to end (`/batch/` with the new token and the
  event seen in PostHog) was not checked: `/flags/` only proves the region knows the
  token.
- `make test` as a whole was not run locally; CI ran unit and integration on 3.10 and
  3.13, green.
