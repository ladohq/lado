Task: LAD-36

## Why

Symptom: with sending on, LADO's daily reports and errors never reach the maintainers'
PostHog project. `telemetry.ENDPOINT` is PostHog Cloud EU (`https://eu.i.posthog.com/batch/`),
but `telemetry.PROJECT_TOKEN` is the token of a project in PostHog's US Cloud (project
661952). The EU region knows no such token and drops the events.

Cause: the token was copied from the wrong region's project when usage-telemetry was
built, and nothing could notice: `/batch/` answers a token it does not know like any
other (it takes the request and drops the events later), the unit tests post to a local
endpoint with `TEST_TOKEN`, and no real send ran before the merge (the usage-telemetry
review report says so). Checked by hand on 2026-10-13: `POST
https://eu.i.posthog.com/flags/?v=2` with the old token answers 401 ("The provided API key
is invalid"), with the EU project's token (project 304141) 200.

## What Changes

- `src/lado/telemetry.py`: `PROJECT_TOKEN` becomes the EU project's token,
  `phc_rFSHMWjPbkNL8t5n2pAMCmvMXKHgxct6VPMkfYxbNhUa`. The comment over `ENDPOINT` and
  `PROJECT_TOKEN` names the region and the project (PostHog Cloud EU, project 304141),
  says the token must be of a project in the endpoint's region, and that
  `scripts/check_telemetry.py` checks it.
- `scripts/check_telemetry.py` (new, standard library and `lado.telemetry` only): asks the
  endpoint's own host whether it knows `PROJECT_TOKEN`, one `POST <scheme>://<host>/flags/?v=2`
  with `{"api_key": <token>, "distinct_id": "lado-release-check"}` (no event is created),
  and exits 0 on a 2xx, 1 otherwise with one line that says why.
- `.github/workflows/release.yml`: a step after the tag check, before `make dist` and `uv
  publish`, runs `uv run python scripts/check_telemetry.py`; a refused token or a failed
  check publishes nothing.
- AGENTS.md, Release: one sentence that the Release workflow runs the check before it
  builds, and that it runs locally the same way; Layout's `scripts/` line names the
  script.
- usage-telemetry spec: a requirement that the built-in token belongs to the endpoint's
  region and that a release is not published while that region refuses it.

## Scope

The built-in token, the release-time check of it, and its record in AGENTS.md and the
spec. docs/telemetry.md already says PostHog Cloud EU and stays as it is.

## Out of scope

- The check in CI on every push (`ci.yml`): every push would depend on PostHog's
  availability, an external source of flaky failures; a wrong token can only reach users
  through a release (the human's decision, 2026-10-13).
- A unit test that pins the token's or the endpoint's value: it would be a second copy of
  the constants and could not tell one region's token from another's.
- Moving the token out of the package or behind a server of LADO's own: a PostHog project
  token is public and write-only by design (it can send events, never read data), and an
  installed LADO must send directly; it is already in every wheel, sdist and the public
  repository.
- A CHANGELOG.md line: usage statistics are not released yet (they come in 0.37.0, whose
  telemetry line stands), so no user ever had the wrong token.

## Acceptance criteria

- AC-1: `telemetry.PROJECT_TOKEN` is `phc_rFSHMWjPbkNL8t5n2pAMCmvMXKHgxct6VPMkfYxbNhUa`,
  next to `ENDPOINT` under one comment naming PostHog Cloud EU, project 304141, the
  same-region rule and `scripts/check_telemetry.py`.
- AC-2: `uv run python scripts/check_telemetry.py` run against the real endpoint prints
  `telemetry: eu.i.posthog.com accepts the project token` and exits 0.
- AC-3: Against a host that answers 401 or 403 it prints `telemetry: <host> refuses the
  project token: it is not a token of a project in this region` and exits 1; against no
  answer, a timeout (10 s), another non-2xx answer or an empty token it prints
  `telemetry: cannot check the project token: <reason>` and exits 1. Unit tests against a
  local HTTP server prove each, with no network.
- AC-4: The Release workflow runs the script after the tag check and before `make dist`
  and `uv publish`; a unit test reads `release.yml` and checks that order.
- AC-5: AGENTS.md (Release, Layout) and the usage-telemetry spec say so; `openspec
  validate posthog-eu-token --strict`, `make lint` and `make test` pass.

## Impact

- `src/lado/telemetry.py`, `scripts/check_telemetry.py` (new),
  `tests/test_check_telemetry.py` (new), `.github/workflows/release.yml`, AGENTS.md.
- No API, schema, MCP or CLI change: a fix inside 0.37.0, no version bump of its own
  (alone it would be a patch).

## Decisions for the record

- Scale hotfix: a defect with a clear symptom and a cause confirmed against PostHog;
  review by precision.
- The check asks `/flags/?v=2` of the endpoint's host: it answers 401 to a token its
  region does not know and 200 to one it knows (checked by hand), while `/batch/` takes
  any token; `/flags` evaluates feature flags (LADO has none) and stores no event.
- The host comes from `telemetry.ENDPOINT` and the token from `telemetry.PROJECT_TOKEN`
  (one source of truth): the script checks exactly the pair that goes into the package.
- Anything but a 2xx fails the release, also "cannot check": a release with an unchecked
  token is the defect this change closes; a PostHog outage costs a rerun of the job.
- 401 and 403 are "refused", every other failure "cannot check", so the line tells a
  wrong token from a network problem.
- The script lives in `scripts/` like `smoke_ci.py` and is loaded by its test through
  `importlib`; it ships in the sdist (all of `scripts/` does) and not in the wheel. No
  secret is in it.
- Test layer: unit (`make test`), a local `http.server` in a thread for the answers and a
  read of `release.yml` (PyYAML, as `tests/test_ci_workflow.py`) for the step's place; the
  real endpoint is checked by hand once (AC-2) and by every release.
