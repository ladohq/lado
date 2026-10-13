## 1. The token

- [x] 1.1 `src/lado/telemetry.py`: `PROJECT_TOKEN = "phc_rFSHMWjPbkNL8t5n2pAMCmvMXKHgxct6VPMkfYxbNhUa"`;
  the comment over `ENDPOINT` and `PROJECT_TOKEN` names PostHog Cloud EU, project 304141,
  says the token must be of a project in the endpoint's region (a token of another region
  is taken by `/batch/` and dropped) and that `scripts/check_telemetry.py` checks it at
  each release (AC-1). Check: `grep -rn phc_tid47 .` finds nothing outside the archive.

## 2. The check

- [x] 2.1 `scripts/check_telemetry.py`: standard library and `lado.telemetry` only;
  `check(endpoint, token, timeout=10) -> tuple[bool, str]` posts
  `{"api_key": token, "distinct_id": "lado-release-check"}` as JSON to
  `<scheme>://<netloc>/flags/?v=2` of `endpoint`; 2xx: `telemetry: <host> accepts the
  project token`; 401 or 403: `telemetry: <host> refuses the project token: it is not a
  token of a project in this region`; an empty token, any other answer, a URL or network
  error or a timeout: `telemetry: cannot check the project token: <reason>`. `main()`
  prints the line and returns 0 or 1 for `telemetry.ENDPOINT` and
  `telemetry.PROJECT_TOKEN`. A docstring says what it is for and that the Release
  workflow runs it (AC-2, AC-3).
- [x] 2.2 `tests/test_check_telemetry.py` (loads the script by `importlib`, as
  `tests/test_smoke_ci.py`): a local `http.server` on 127.0.0.1 and a free port in a
  thread; 200 accepts and the request was a POST to `/flags/?v=2` with the token and the
  fixed `distinct_id`; 401 and 403 refuse; 500 and a closed port cannot check; an empty
  token cannot check and sends nothing; a server that does not answer within a short
  timeout cannot check (AC-3). Check: `make test`.
- [x] 2.3 By hand, once: `uv run python scripts/check_telemetry.py` prints the accept line
  and exits 0 (AC-2); the build report quotes it.

## 3. The release

- [x] 3.1 `.github/workflows/release.yml`: a step `Check the telemetry token belongs to
  the endpoint's region`, `run: uv run python scripts/check_telemetry.py`, after `Check
  tag matches package version` and before `make dist` and `uv publish` (AC-4).
- [x] 3.2 `tests/test_check_telemetry.py`: reads `release.yml` with PyYAML and checks that
  the step runs the script and comes after the tag check and before `make dist` and `uv
  publish` (AC-4). Check: `make test`.
- [x] 3.3 AGENTS.md: Release says the Release workflow first runs
  `scripts/check_telemetry.py` (the telemetry token is one its endpoint's region accepts)
  and that it runs locally as `uv run python scripts/check_telemetry.py`; Layout's
  `scripts/` line names it (AC-5).
- [x] 3.4 `openspec validate posthog-eu-token --strict`, `make lint` and `make test` pass.
