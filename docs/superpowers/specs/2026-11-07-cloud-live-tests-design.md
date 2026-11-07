# Live tests on a cloud model, in CI

Task: LAD-231. Change: `openspec/changes/cloud-live-tests/` (why and scope in its `proposal.md`,
the rules in its delta, the decisions D1 to D16 in its `design.md`). This document says how the
pieces fit and what the human does by hand.

## Shape

```
the trial, first, by hand, on the code as it stands
  └─ Codex direct: cheap model, OpenAI model. Both fail: stop, the human chooses, redesign.
  └─ Claude Code: haiku, then a cheap model. Both fail: stop, the human decides.
  └─ OpenCode, Kilo, three full runs
then, only after it worked:
  LM Studio, LiteLLM and Claude's own login go; one setup left, an entry per provider

schedule (Mon 04:23 UTC) / dispatch
  └─ live.yml, environment `live` (main, tags v*)
       └─ cell per provider, each with its model (ubuntu)
            └─ scripts/smoke_ci.py live <provider> <out>
                 ├─ install the CLI at its pin (three attempts, as the smoke)
                 ├─ timeout 1500 pytest -m live ... into a temp folder, not <out>
                 ├─ pass only with a pass and no skip
                 └─ redact the key there, then move the files to <out>; the workflow uploads <out>

OpenCode, Kilo ── chat completions (/api/v1) ──┐
Codex ─────────── Responses (/api/v1) ─────────┼─ OpenRouter ─ cheap models
Claude Code ───── Anthropic Messages (/api) ───┘
```

`LADO_LIVE_ENDPOINT` is `https://openrouter.ai/api/v1` in `live.yml`, and no default anywhere else:
without it, its key and a model, the live tests skip and name what to set.
`LADO_LIVE_IMAGE=1`, and `LADO_LIVE_MODEL` the matrix's model of the cell. All the tests of
`tests/live/test_live.py` run for each provider.

Adding a provider: an entry in `live_models.SETUPS`, a pin in `smoke_ci.py`, a line in the matrix;
the unit tests name what is missing.

## The workflow

One job `live`, `if: github.repository == 'ladohq/lado'` (a fork's schedule has no secret),
`environment: live`, `timeout-minutes: 30`, `fail-fast: false`, `permissions: contents: read`,
`concurrency: {group: live, cancel-in-progress: false}`. The matrix is an `include` list of
`{provider, model}`, and the test step passes `LADO_LIVE_MODEL: ${{ matrix.model }}`. Checkout with
`persist-credentials: false`, as an agent with a shell runs on the runner. Setup as ci.yml's smoke
job on Linux. `LADO_LIVE_API_KEY: ${{ secrets.LADO_LIVE_API_KEY }}` stands in the `env` of the test
step alone. Upload `if: always()`, retention 5 days.

## What the human does

Nothing here is an agent's: keys are the human's, and a value never passes through an agent.

**Before the trial**

1. On openrouter.ai, Settings, API Keys: create the key `lado-live-trial`, credit limit $5.
2. Give it to the project, in your own terminal, not in a chat with an agent:
   `lado project set <project id> OPENROUTER_LIVE_KEY --secret`, and paste the key when asked (or
   the UI's project page). Agents started after this get it; a running developer is restarted.
3. Say yes to the trial when the card comes.

**After the trial**

4. `lado project unset <project id> OPENROUTER_LIVE_KEY`, and delete the key on openrouter.ai.

**Before the first CI run** (any time; you have admin rights on the repository)

5. Create the key `lado-live-ci`, limit $10, reset monthly.
6. Create the environment `live`, with deployments only from `main` and tags `v*`:

   ```bash
   gh api -X PUT repos/ladohq/lado/environments/live --input - <<'EOF'
   {"deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
   EOF
   gh api -X POST repos/ladohq/lado/environments/live/deployment-branch-policies -f name=main -f type=branch
   gh api -X POST repos/ladohq/lado/environments/live/deployment-branch-policies -f name='v*' -f type=tag
   ```

   Or in the browser: Settings, Environments, New environment `live`, Deployment branches and tags:
   Selected, add branch `main` and tag `v*`. No required reviewers.
7. Put the key in it, `gh secret set LADO_LIVE_API_KEY --env live --repo ladohq/lado`, and paste
   the key when asked (with no `--body`, so it stays out of the shell's history).
8. Check: `gh api repos/ladohq/lado/environments/live/deployment-branch-policies --jq
   '.branch_policies[] | "\(.type) \(.name)"'` prints `branch main` and `tag v*`.

**After the merge**

9. Press the button: `gh workflow run live.yml`, or Actions, Live tests, Run workflow. This first
   run closes AC-3. `gh run list --workflow live.yml` shows it.

## A red run

GitHub mails it. Open the run: a cell's log names the test, and its artifact holds the evidence.
Rerun the failed cells by hand (`gh run rerun <id> --failed`). A pass on a rerun is a flake, noted
as the project's rule says; a 402 means the month's limit is spent.

## Tests per requirement

| Requirement | Layer | Where |
|---|---|---|
| Live tests run weekly and by hand outside ci-ok | unit | `tests/test_live_workflow.py` |
| The live key reaches only main and tags | unit (files), GitHub (the rule, step 8) | `tests/test_live_workflow.py` |
| A live cell passes only with a pass and no skip | unit | `tests/test_smoke_ci.py` |
| What a live cell uploads holds no key | unit | `tests/test_smoke_ci.py` |
| Every provider's live tests run only on a remote endpoint | unit; live in the trial | `tests/test_live_models.py` |
| A release candidate's live check is the live workflow | document, checked at the next RC | docs/release.md |

No integration test: nothing of LADO's processes changes; the real crossing is the live layer
itself, which the trial runs end to end. Regression: `make test`, `make lint`, and the three test
files alone first.
