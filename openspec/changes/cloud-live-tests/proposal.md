Task: LAD-231

## Why

The live tests (`tests/live/`, `make test-live`) run only by hand before a release. Codex,
OpenCode and Kilo run in them on a local model in LM Studio, which needs a machine with about
64 GB of memory, so the runs are rare and hang on one machine: 0.34.0 went out with none at all,
as no local model passed the Codex tests (BACKLOG.md). CI has only the smoke, whose model is a
401 stub, so no real turn of a model is checked in CI.

Root cause: the only model these three providers can reach in a test sits on one person's
machine, and the rule "never a paid model" (docs/testing.md, from 2026-10-11, its reason recorded
nowhere) closes the other way. The remote endpoint support of that commit
(`LADO_LIVE_ENDPOINT`) already exists.

Codex is the one gap. It sends MCP tools as one `namespace` entry, which is no part of the
standard Responses API; openai/codex issues #32318 and #26234 (both open) report OpenRouter
answering 400 "No endpoints found that support the native namespace tool type". Not yet measured
here: the trial answers it. `local_models.Bridge` solves the same problem for LM Studio but is
fixed to LM Studio, with no key.

Options weighed:

- A (taken): a cheap cloud model on OpenRouter with a limited key, in a workflow of its own.
  Checks real turns on any runner. Cost: a few dollars a month, a key to keep, red runs from a
  provider's outages.
- B: a fake model server in the smoke (BACKLOG.md, "A fake model server for the smoke tests").
  Free and steady, but it answers canned replies, so it never shows that a real model copes with
  LADO's tools, and each API's shape has to be kept up by hand. It stays a separate item.
- C: a self-hosted runner with LM Studio. No token cost, but it keeps the dependency on one
  64 GB machine, and a self-hosted runner on a public repository is a risk of its own.

## What Changes

- **A trial on OpenRouter**, by hand, with the human's yes and a key of its own: Codex (direct,
  then through the bridge), OpenCode, Kilo. Its report gives providers and scenarios, model, cost
  and stability, and fixes the model and the bridge setting the workflow uses.
- **The bridge reaches a remote endpoint.** `local_models.Bridge` takes the upstream's key by
  reference; `LADO_LIVE_CODEX_BRIDGE=1` sends Codex through it to `LADO_LIVE_ENDPOINT`.
- **A workflow `.github/workflows/live.yml`**: weekly on main and by hand, a cell per provider
  (Codex, OpenCode, Kilo) on Linux, outside `ci.yml`, so outside `ci-ok`.
- **The key** is a secret of the GitHub environment `live`, open only to `main` and tags `v*`;
  a run of a pull request cannot get it.
- **`scripts/smoke_ci.py live`**: a cell with the smoke's install and pass rule, and the key's
  value redacted from all it leaves for upload, as this repository's artifacts are public.
- **The rule on paid models changes**: docs/testing.md and AGENTS.md's Testing say what is true
  now. A paid model only with a limited key and the human's yes; the schedule in CI is that yes,
  given once by this task; Claude Code stays "only with the human's yes".

## Scope

In: the trial and its report, the bridge's remote upstream, `live.yml`, the `live` cell of
`scripts/smoke_ci.py`, their unit tests, docs/testing.md, AGENTS.md's Testing,
`tests/live/conftest.py`'s docstring.

## Out of scope

- Whether the release's LM Studio step changes (docs/release.md): decided separately, on the
  results; the task says so.
- Claude Code on a subscription and `tests/live/test_codex_login.py`: they need a human's login
  and stay local.
- macOS cells: the cost doubles, and the smoke already covers how the CLIs start per system.
- Automatic retries of a red cell: the project's rule is a rerun by hand; a pass on a rerun is a
  flake. Telling a provider's outage from LADO's failure stays an open BACKLOG.md item.
- cloud.ru: no confirmation of its Responses API and tool calls; the same bridge can reach it
  later.
- A schedule more often than weekly: a month of runs decides.
- `.lado/sdlc.md` (its "run only at a release" on `make test-live`): the human keeps that file.

## Impact

- `tests/local_models.py`, `tests/live/conftest.py`, `scripts/smoke_ci.py`,
  `.github/workflows/live.yml` (new); `tests/test_local_models.py`, `tests/test_smoke_ci.py`,
  `tests/test_live_workflow.py` (new).
- docs/testing.md, AGENTS.md.
- LADO itself does not change: no CHANGELOG.md line, no version bump of its own.
- The human: two keys, the environment and its secret (design.md D9).
