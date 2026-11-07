Task: LAD-231

## Why

The live tests (`tests/live/`, `make test-live`) run only by hand before a release. Codex,
OpenCode and Kilo run in them on a local model in LM Studio, which needs a machine with about
64 GB of memory, and Claude Code on the human's own subscription, so the runs are rare and hang
on one machine and one person: 0.34.0 went out with none at all,
as no local model passed the Codex tests (BACKLOG.md). CI has only the smoke, whose model is a
401 stub, so no real turn of a model is checked in CI.

Root cause: the only models the providers can reach in a test sit on one person's machine or
login, and the rule "never a paid model" (docs/testing.md, from 2026-10-11, its reason recorded
nowhere) closes the other way. The remote endpoint support of that commit
(`LADO_LIVE_ENDPOINT`) already exists.

Codex is the one gap. It sends MCP tools as one `namespace` entry, which is no part of the
standard Responses API; openai/codex issues #32318 and #26234 (both open) report OpenRouter
answering 400 "No endpoints found that support the native namespace tool type". Not yet measured
here, and it may depend on the model behind OpenRouter: the trial answers it, first thing, before
any code of this change.

LM Studio and the subscription leave the live tests with this change, once the trial has shown
that the cloud setup works: all four providers then run the same way, on one key, and a new
provider joins as one more entry. Keeping either means keeping a second setup, its checks and, for
LM Studio, the LiteLLM bridge.

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

- **A trial on OpenRouter comes first**, by hand, with the human's yes and a key of its own, on
  the code as it stands, with `claude` set by hand: Codex direct on a cheap model and on an
  OpenAI model, Claude Code on a cheap Anthropic model, then OpenCode and Kilo. Its report gives providers and scenarios, model, cost and stability,
  and fixes the models the workflow uses.
- **One setup for four providers**, after a trial with a working path for each: LM Studio, the
  bridge and Claude Code's personal login and config leave `tests/local_models.py` (renamed
  `tests/live_models.py`), `tests/live/conftest.py`, their tests and docs/testing.md. Each provider
  has one entry that sets it up on the endpoint. The endpoint has no default value: without
  `LADO_LIVE_ENDPOINT`, its key and a model, the live tests skip, saying what to set.
- **A workflow `.github/workflows/live.yml`**: weekly on main and by hand, a cell per provider
  (Claude Code, Codex, OpenCode, Kilo) with its own model on Linux, outside `ci.yml`, so outside `ci-ok`.
- **The key** is a secret of the GitHub environment `live`, open only to `main` and tags `v*`;
  a run of a pull request cannot get it.
- **`scripts/smoke_ci.py live`**: a cell with the smoke's install and pass rule. It works outside
  the uploaded folder and moves its files there only after the key's value is redacted, as this
  repository's artifacts are public.
- **The release's live step** (docs/release.md, section 2, step 3) is rewritten, as without the old
  setups `make test-live` would skip every provider and end without a failure: `live.yml` on the
  RC's commit, checked by the run's commit, and nothing local.
- **The rule on paid models changes**: docs/testing.md and AGENTS.md's Testing say what is true
  now. A paid model only with a limited key and the human's yes; the schedule in CI is that yes,
  given once by this task. "Claude Code only with the human's yes" goes: no subscription and no
  Anthropic key are used for tests any more.

## Scope

In: the trial and its report, the removal of LM Studio and LiteLLM, `live.yml`, the `live` cell of
`scripts/smoke_ci.py`, their unit tests, docs/testing.md, docs/release.md, AGENTS.md's Testing.

## Out of scope

- A bridge to OpenRouter or a direct OpenAI key, for Codex: only when Codex fails on both models of the
  trial. The human left that choice for then, and the design comes back with it.
- `tests/live/test_codex_login.py`: it tests a real ChatGPT login's refresh, needs a Codex home a
  human logged in to, and stays local.
- An Anthropic key as Claude Code's fallback: the human turned it down.
- macOS cells: the cost doubles, and the smoke already covers how the CLIs start per system.
- Automatic retries of a red cell: the project's rule is a rerun by hand; a pass on a rerun is a
  flake. Telling a provider's outage from LADO's failure stays an open BACKLOG.md item.
- cloud.ru: no confirmation of its Responses API and tool calls.
- A schedule more often than weekly: a month of runs decides.
- `.lado/sdlc.md` (its "run only at a release" on `make test-live`): the human keeps that file.

## Impact

- `tests/local_models.py` becomes `tests/live_models.py`, `tests/test_local_models.py`
  `tests/test_live_models.py`; `tests/live/conftest.py`, `tests/live/test_live.py`, `tests/real_clis.py`,
  `scripts/smoke_ci.py`, `.github/workflows/live.yml` (new); `tests/test_smoke_ci.py`,
  `tests/test_live_workflow.py` (new), `tests/test_workflow_security.py`.
- docs/testing.md, docs/release.md, AGENTS.md; two BACKLOG.md entries on LM Studio get a line.
- LADO itself does not change: no CHANGELOG.md line, no version bump of its own.
- The human: two keys, the environment and its secret (design.md D9).
