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
of D4 makes that rare. Retention 5 days, as the smoke's.

**D6. The trial decides Codex's route, before any code.** The issues say a direct path may fail,
but the error comes from routing, so an OpenAI model behind OpenRouter may pass where another
fails. The trial needs no code: `LADO_LIVE_ENDPOINT` with no bridge already exists.

- One path works: LiteLLM goes entirely, with LM Studio, and Codex uses that path's model
  (`LADO_LIVE_CODEX_MODEL` in `live.yml` when it differs from the others').
- Both fail: the developer stops and asks the human through the supervisor: a bridge to OpenRouter
  or a direct OpenAI key. Either answer changes this delta, so the run comes back here by
  `redesign`, and nothing of LM Studio or LiteLLM is removed before it.

A shim of our own that flattens `namespace` was rejected: it is the bridge again, with code to keep
up as Codex changes.

**D7. LM Studio goes after the trial, not before.** The task order keeps a working setup until
the new one has passed. Gone: `MODEL`, `lmstudio_*`, `write_lmstudio_config`, `Bridge`, `LITELLM`,
`CODEX_BASE_URL` and its `LADO_LIVE_CODEX_BASE_URL`, `LADO_LIVE_LMSTUDIO_URL`, `codex_bridge`,
`BRIDGES`, `LOCAL`, `lmstudio_model`. `endpoint_problem` also covers an unset endpoint, so a skip
names the three variables. `declared_vision` goes by `LADO_LIVE_IMAGE` alone. The module is
renamed `tests/live_models.py`, as `local_models` would now mislead. `model_provider = "lmstudio"`
in `tests/test_login_status.py` is a sample of a user's Codex config and stays, as does the
historical note in docs/design/agents.md. A local server can still serve as `LADO_LIVE_ENDPOINT`.

**D8. The models: `qwen/qwen3.7-flash`, then `openai/gpt-5-nano`.** Both declare tools and images on
OpenRouter, at $0.03 in and $0.13 out and at $0.05 and $0.40 per million tokens. The second is the
OpenAI model D6 needs. `qwen/qwen3.5-35b-a3b`, the first design's fallback, is dropped: BACKLOG.md
records it answering tool calls as text, OpenCode red in 3 of 3 runs. The cheapest that passes
goes into `live.yml` as `LADO_LIVE_MODEL`, the one place it is written. A run is estimated at $0.06
to $0.30, from about 2 million input tokens; that is an estimate, not a measurement, and the
trial replaces it.

**D9. Keys and setup: what the human does.** Two keys, never `OPENROUTER_API_KEY` of the agents'
environment, which is the human's own development key.

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
Order: one Codex test direct on each model (D6); then every provider on the first model that
works for it; then three full runs of the chosen setup for stability. Spending is read from the
key's usage before and after (`GET /api/v1/key`, the key from the environment, never printed). At
$4 spent it stops. When OpenCode or Kilo fails on both models, the developer stops and reports
`redesign`: leaving a provider out quietly is a silent drop, and the human decides.

**D11. The first dispatch comes after the merge.** GitHub offers dispatch only for a workflow on
the default branch, and the environment admits only `main`. Before the merge the workflow is
proved by unit tests and by the trial's same pytest command; the human presses the button after
the merge, and that run closes AC-3.

**D12. No version of its own.** No user of LADO sees a change, so no CHANGELOG.md line and no minor
bump; by AGENTS.md's rule this counts as a patch-level change (tests and docs).

**D13. The release's live step is `live.yml` on the RC's commit.** The human's choice. Without LM
Studio a local `make test-live` skips three providers and ends with no failure, so it cannot stay.
The RC's commit is on `main` before the tag (docs/release.md, section 2), which the environment
admits. A red cell follows the flaky rule; Claude Code stays local with the human's yes.

**Against the principles.** Neutral core: three providers run; Claude Code is left out and said
to be, as it needs a subscription login. One source of truth: one setup instead of two, the model stands once
in `live.yml`, the CLI pins stay in `smoke_ci.py`. No silent drops: a skip is red, a provider that
cannot pass goes to the human. Only what is used: no provider input on dispatch, as a rerun of
failed jobs covers it. Roadmap: the coming stages (cloud workers) add nothing here that this
would block.
