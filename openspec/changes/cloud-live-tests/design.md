## Decisions

**D1. A workflow of its own, not a job of ci.yml.** `tests/test_ci_ok.py` makes `ci-ok` need every
job of `ci.yml`, and a provider's 503 must not block a merge. `live.yml` follows the Windows
probe's shape: schedule plus dispatch, a red run mails as any failed workflow does (to whoever
last changed the cron line).

**D2. Weekly, Monday 04:23 UTC, plus dispatch.** The human's choice: a daily run costs about seven
times as much, and daily mails from outages teach people not to read them. The minute avoids
ci.yml's 03:47 and the Windows probe's Monday 03:17.

**D3. The key in the environment `live`, deployment rule `main` and tags `v*`.** A repository
secret would reach any workflow a branch adds. A dispatch on any other ref, and any pull request
ref, is refused the environment by GitHub, not by this repository's files, so a pull request
cannot lift it. The unit tests guard the triggers as a second line. Tags are in so that a release
candidate can be checked by `gh workflow run live.yml --ref <tag>`. No required reviewer: it would
stop the schedule.

**D4. The cell is `scripts/smoke_ci.py live`.** It reuses the install with retries and `cell`'s
pass rule; `run` is split so that install is one function. A second script would copy both. The
name of the file stays: renaming it touches ci.yml, the Windows probe and their tests for no
behaviour. Its command: `timeout --kill-after=30 1500 uv run pytest -m live -n0 -v -k <provider>
--ignore=tests/live/test_codex_login.py`, the 25 minutes under the job's 30 so that a hang still
leaves a log and evidence; without the ignore that file's skip would fail every
Codex cell by the pass rule.

**D5. The cell works outside the uploaded folder.** `keep_evidence` redacts the evidence, but the
pytest log is not covered, GitHub's masking does not apply to uploaded files, and artifacts of a
public repository can be downloaded by anyone. An agent has a shell, so a model may print its
environment. A redaction after the tests is not enough on its own: `cell` writes its log as it
goes, and a job killed at its timeout, or a crash, would leave an unredacted log for the upload's
`if: always()` (the supervisor's review of the first design). So `live` gives `cell` a folder of
`tempfile.mkdtemp()`, redacts there, on bytes, as `agent_helpers.keep_evidence` does (the script
imports nothing of LADO, so it has its own few lines), and only then moves the files to `<out>`.
Killed before that, nothing is uploaded; the evidence of that run is lost, and the 25-minute limit
of D4 makes that rare. Retention 5 days, as the smoke's. A window wraps what it shows, and GitHub's
mask needs the whole value, so `redact` finds the value with non-key characters between its own,
and the job's log gets the test log only after it (the review's F2): a running cell is silent.

**D6. The trial decides Codex's and Claude Code's routes, before any other code.** The issues say a direct path may fail,
but the error comes from routing, so an OpenAI model behind OpenRouter may pass where another
fails. For Codex the trial needs no code: `LADO_LIVE_ENDPOINT` with no bridge already exists. For
Claude Code it sets the variables of D14 by hand around `LADO_LIVE_CLAUDE_MODEL`, in a shell with
a config folder of its own; no code either.

- One path works: LiteLLM goes entirely, with LM Studio, and Codex uses that path's model
  (`LADO_LIVE_CODEX_MODEL` in `live.yml` when it differs from the others').
- Both fail: the developer stops and asks the human through the supervisor: a bridge to OpenRouter
  or a direct OpenAI key. Either answer changes this delta, so the run comes back here by
  `redesign`, and nothing of LM Studio or LiteLLM is removed before it.

Claude Code fails on both its models (D8): the developer stops and asks the human through the
supervisor. An Anthropic key is no fallback: the human turned it down. A dearer model needs their
yes, as one test of `claude-sonnet-5.5` costs some twenty times one of haiku.

A shim of our own that flattens `namespace` was rejected: it is the bridge again, with code to keep
up as Codex changes.

**D7. LM Studio goes after the trial, not before; so does Claude's own setup.** The task order keeps a working setup until
the new one has passed. Gone: `MODEL`, `lmstudio_*`, `write_lmstudio_config`, `Bridge`, `LITELLM`,
`CODEX_BASE_URL` and its `LADO_LIVE_CODEX_BASE_URL`, `LADO_LIVE_LMSTUDIO_URL`, `codex_bridge`,
`BRIDGES`, `LOCAL`, `lmstudio_model`. `endpoint_problem` also covers an unset endpoint, so a skip
names the three variables. `declared_vision` goes by `LADO_LIVE_IMAGE` alone, for all four. Gone for Claude Code too:
`_claude_unusable`, `CLAUDE_REPO` (a fixed path was there for the human's config) and the `delenv`
of `CLAUDE_CONFIG_DIR`, so the autouse `claude_config` of `tests/conftest.py` holds the test's clean
config, as in every other layer. The module is
renamed `tests/live_models.py`, as `local_models` would now mislead. `model_provider = "lmstudio"`
in `tests/test_login_status.py` is a sample of a user's Codex config and stays, as does the
historical note in docs/design/agents.md. A local server can still serve as `LADO_LIVE_ENDPOINT`.

**D8. The models, one per cell.** Prices per million tokens on OpenRouter, in and out:

| Provider | First | Then |
|---|---|---|
| OpenCode, Kilo | `qwen/qwen3.7-flash` ($0.03, $0.13) | `openai/gpt-5-nano` ($0.05, $0.40) |
| Codex | `qwen/qwen3.7-flash` | `openai/gpt-5-nano`, the OpenAI model D6 needs |
| Claude Code | `anthropic/claude-haiku-5.5` ($0.10, $0.50; cached $0.01) | `qwen/qwen3.7-flash` |

All declare tools and images. OpenRouter guarantees Claude Code only with Anthropic's own models,
so haiku comes first. `qwen/qwen3.5-35b-a3b`, the first design's fallback, is dropped: BACKLOG.md
records it answering tool calls as text, OpenCode red in 3 of 3 runs.

`live.yml`'s matrix names provider and model together (`include`), and the step passes
`LADO_LIVE_MODEL: ${{ matrix.model }}`: Claude Code will hardly share a model with the others, the
model has one place, and no per-CLI variable is needed there. After the trial the developer writes
each provider's cheapest passing model into the matrix.

Budget, all estimates until the trial measures them: a full run of four providers is about 3
million input tokens, $0.20 to $0.50. A month of 4 or 5 weekly runs, a few release candidates and
reruns is about 10 runs, $2 to $5: within $10. The trial is about 5 full runs, $1 to $2.50: within
$5, and the stop at $4 stays.

**D9. Keys and setup: what the human does.** Two keys, never `OPENROUTER_API_KEY` of the agents'
environment, which is the human's own development key. In the event the human allowed that key at
the design's gate, and the trial ran on it, with its limit of $5, instead of a key of its own.

- The trial's key, limit $5: a project secret `OPENROUTER_LIVE_KEY`, set by the human
  (`lado project set <id> OPENROUTER_LIVE_KEY --secret`), so an agent of the project gets it at
  its start; `LADO_LIVE_API_KEY` itself cannot be one, as LADO's prefix is reserved. The developer
  runs `LADO_LIVE_API_KEY="$OPENROUTER_LIVE_KEY" make test-live ...`. The human removes the
  secret and the key after the trial, since every agent of the project can read it.
- The CI key, limit $10 a month: only in GitHub, never in LADO. Its limit is the hard stop: past
  it a run goes red with a payment error.
- The environment and its secret: docs/superpowers/specs/2026-11-07-cloud-live-tests-design.md,
  "What the human does", with exact commands.

**D10. The trial stops by money and by result.** It starts only on the human's separate yes.
Order: one Codex test and one Claude Code test on each of their models (D6); then every provider
on the first model that works for it; then three full runs of the chosen setup for stability. Spending is read from the
key's usage before and after (`GET /api/v1/key`, the key from the environment, never printed). At
$4 spent it stops. When OpenCode or Kilo fails on both models, the developer stops and reports
`redesign`: leaving a provider out quietly is a silent drop, and the human decides.

**D11. The first dispatch comes after the merge.** GitHub offers dispatch only for a workflow on
the default branch, and the environment admits only `main`. Before the merge the workflow is
proved by unit tests and by the trial's same pytest command; the human presses the button after
the merge, and that run closes AC-3.

**D12. No version of its own.** No user of LADO sees a change, so no CHANGELOG.md line and no minor
bump; by AGENTS.md's rule this counts as a patch-level change (tests and docs).

**D13. The release's live step is `live.yml` on the RC's commit.** The human's choice. Without the
old setups a local `make test-live` skips every provider and ends with no failure, so it cannot
stay. The RC's commit is on `main` before the tag (docs/release.md, section 2), which the
environment admits. The button runs whatever `main` is at, so the step checks that the run's SHA
is the RC's: `gh run list --workflow live.yml --limit 1 --json headSha,conclusion`. A red cell
follows the flaky rule.

**D14. One entry per provider.** `live_models.SETUPS` maps a provider to a function `(model, folder)
-> variables`: Codex's writes its config, OpenCode's and Kilo's their file, Claude Code's only
returns variables. `live_provider` has no branch on a provider: it clears the login variables (the
smoke's list), runs the entry, sets what it returns. `MODELS` and the skip reason come from the
same names, the fixture's params from `SETUPS`. A new CLI is one entry here, one pin in
`smoke_ci.py`, one line in the matrix, and the tests name a missing one. The list of providers in
the cell is `PINS` itself. What stays per provider in `test_live.py` is
what the CLIs really differ in (`/clear`, tool checks); it is not setup. No registry or class: a
dict of four functions is all four need.

**D15. Claude Code on OpenRouter.** By OpenRouter's Claude Code guide: `ANTHROPIC_BASE_URL` is
`https://openrouter.ai/api`, so `endpoint().removesuffix("/v1")`, and the key goes as
`ANTHROPIC_AUTH_TOKEN`, a bearer token. Not `ANTHROPIC_API_KEY`: Claude Code takes that for a direct
Anthropic key, and one it has not seen is a question; a token is taken without asking, as the
smoke proves at the pinned version, and LADO's `approve_key` is not involved. The guide wants
`ANTHROPIC_API_KEY` empty; here the test's environment has none, as the login variables are
cleared. The model goes as `ANTHROPIC_MODEL`, with `ANTHROPIC_DEFAULT_HAIKU_MODEL` the same, as
Claude Code's background calls name a haiku of their own, which OpenRouter would refuse or bill
elsewhere; so `with_model` goes from the live tests when nothing else uses it. Also
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, as in the smoke. The key is a value in the environment
here, not a reference: Claude Code has no other way, and the redaction of D5 covers it. The checks
that LADO's tools are there and not deferred stay, so a weak model's behaviour shows; `check_models`
gains Claude Code, by each transcript's `message.model`, as a model silently ignored would cost
money and prove the wrong thing.

**D16. What the subscription's absence leaves uncovered.** The human's decision, recorded here. No
live test uses a Claude subscription any more. Still covered: the login check's logic and
`CLAUDE_CODE_OAUTH_TOKEN` in unit tests (`tests/test_login_status.py`, `tests/test_agent_env.py`);
trust, onboarding and the start without a dialog by the smoke on Linux and macOS with the real CLI;
a whole turn with real tools by the live cell. The gap: a real subscription login end to end, that
is the keychain and the macOS graphical session (`gui_session.py`), a real token's refresh, a
human's own `.claude.json`, and Anthropic's API itself with its limits, as OpenRouter stands
between. The human's daily use of LADO on a subscription is the only check of those, and a break
there shows only then.

**Against the principles.** Neutral core: all four providers run the same way, nobody excepted. One source of truth: one setup instead of two, the model stands once
in `live.yml`, the CLI pins stay in `smoke_ci.py`. No silent drops: a skip is red, a provider that
cannot pass goes to the human. Only what is used: no provider input on dispatch, as a rerun of
failed jobs covers it; no framework for providers, a dict. Roadmap: the coming stages (cloud workers) add nothing here that this
would block.
