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
behaviour. Its command: `uv run pytest -m live -n0 -v -k <provider>
--ignore=tests/live/test_codex_login.py`; without the ignore that file's skip would fail every
Codex cell by the pass rule.

**D5. Redaction over the whole output folder.** `keep_evidence` redacts the evidence, but the
pytest log, which the cell writes, is not covered, GitHub's masking does not apply to uploaded
files, and artifacts of a public repository can be downloaded by anyone. An agent has a shell, so
a model may print its environment. `live` runs the replacement last, on bytes, on every file
under `<out>`, the same way as `agent_helpers.keep_evidence` (the script imports nothing of LADO,
so it has its own few lines). Retention 5 days, as the smoke's.

**D6. Codex's route is a switch, `LADO_LIVE_CODEX_BRIDGE=1`.** The issues say the bridge will be
needed, but a measurement should settle it, and `LADO_LIVE_ENDPOINT` also serves endpoints that
keep the tools (a LiteLLM gateway, docs/testing.md), so always bridging would change them. A shim
of our own that flattens `namespace` was rejected: it is the bridge again, with code to keep up as
Codex changes. The bridge's Chat translation is already proved on LM Studio.

**D7. The bridge's upstream is a full base URL.** `Bridge.start(folder, upstream, model,
command=LITELLM, key_variable=None)`: `upstream` ends in `/v1` (the fixture passes
`f"{lmstudio_url()}/v1"` or `endpoint()`), and `api_key` in its config is
`os.environ/<key_variable>`, LiteLLM's reference form, else `none`. The process already inherits
the environment, so the value stays out of the file.

**D8. The model: first `qwen/qwen3.7-flash`, then `qwen/qwen3.5-35b-a3b`.** Both declare tools and
images on OpenRouter. The first costs $0.03 in and $0.13 out per million tokens; the second, at
$0.14 and $1.00, is the local model the tests have passed on. The cheapest that passes the trial
goes into `live.yml` as `LADO_LIVE_MODEL`, the one place it is written, with
`LADO_LIVE_CODEX_BRIDGE` beside it. A run is estimated at $0.06 to $0.30, from about 2 million
input tokens; that is an estimate, not a measurement, and the trial replaces it.

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

**D10. The trial stops by money and by result.** It starts only on the human's separate yes. Order:
one Codex test direct, one with the bridge; then the whole provider set on the first model; then
three full runs of the chosen setup for stability. Spending is read from the key's usage before
and after (`GET /api/v1/key`, with the key from the environment, never printed). At $4 spent it
stops. When a provider fails on both models, the developer stops and reports `redesign`: leaving a
provider out quietly is a silent drop, and the human decides.

**D11. The first dispatch comes after the merge.** GitHub offers dispatch only for a workflow on
the default branch, and the environment admits only `main`. Before the merge the workflow is
proved by unit tests and the same `make test-live` command in the trial; the human presses the
button after the merge, and that run closes AC-3.

**D12. No version of its own.** No user of LADO sees a change, so no CHANGELOG.md line and no minor
bump; by AGENTS.md's rule this counts as a patch-level change (tests and docs).

**Against the principles.** Neutral core: three providers run; Claude Code is left out and said
to be, as it needs a subscription login. One source of truth: the model and the switch stand once
in `live.yml`, the CLI pins stay in `smoke_ci.py`. No silent drops: a skip is red, a provider that
cannot pass goes to the human. Only what is used: no provider input on dispatch, as a rerun of
failed jobs covers it. Roadmap: the coming stages (cloud workers) add nothing here that this
would block; the bridge's remote upstream is what a later endpoint would use.
