# LAD-112 uninstall-waits-for-agents: review report

Pull request #133 `hotfix/lad-112-uninstall-waits-for-agents` → `main`. Scale: hotfix,
reviewed by precision with a breadth pass in round 1, as the path deletes the user's data.
Head reviewed: `c468030` (= the remote head). `providers/`, `hooks.py`, `mcp_server.py`,
`runtime.py`, `agent_env.py` and `tests/live/` did not change; the change touches
`uninstall.py` and `tmux.py` only.

## Rounds

- **Round 1, local** (`origin/main..bd49468`, then the delta `bd49468..41e2259`): lenses
  spec, tests, silent failures, comments/docs, general and the architecture against
  AGENTS.md (types skipped: no new types). Every scenario of the delta is covered,
  tasks.md checked 10 of 10, D1–D6 kept. F1, F2.
- **Round 2, external** (Claude Code GitHub Action; request 20:03:52Z, comment
  issuecomment-6325356814, "Claude finished" 20:04:24Z, comment issuecomment-6325366955,
  on `bd49468`): no blockers, six minor points (F1 merged with point 1, F3–F7). Reply:
  issuecomment-6325598310. It is of the same model family, so its "nothing more" weighs
  less.
- **Round 3, local** (precision, `41e2259..7897acb`, a return from `merge`: the archive was
  refused, as the modified requirement "Everything of this LADO_HOME stops" grew past
  openspec's 500 characters). The rule naming the session, the pids and `kill <pid>` moved
  to an added requirement of its own with its scenario; no code or test changed. A trial
  archive in a copy of `openspec/` gave `+1, ~1`, then `openspec validate --specs
  --strict` 43 of 43. No new findings. No external round: the cap of 1 was used.
- **Round 4, local** (precision, a return from `merge` on conflicts: the merge
  `d0815e0..c468030` of `main` at `fa94d2c`, LAD-122). The merge brings only main's
  changes; the pull request's diff against main without CHANGELOG.md is byte for byte the
  one reviewed before. CHANGELOG.md's `0.43.0 (unreleased)` Fixed keeps both lines
  (LAD-112 and LAD-122). No new findings. No external round: the cap of 1 was used.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (general) + external 1 | `lado uninstall` run again after the timeout no longer waits for the hung agent: its pane is gone after `kill-session` and the session is marked stopped | confirmed | minor | declined: the error says to run `kill <pid>` first; waiting on a rerun needs the pids kept, a second source of truth (D1) |
| F2 | 1 | local (process) | commit `41e2259` was not on the remote | confirmed | important | fixed: pushed, CI green |
| F3 | 2 | external 2 | `tmux.pane_pids` takes any `TmuxError` as "no session", so the wait may be skipped silently | confirmed | minor | declined: the whole module does so (`has_session`, `window_names`, `sessions_with`), `TmuxMissing` still propagates, and a broken socket fails `kill-session` in `stop_all` right after |
| F4 | 2 | external 3 | a pane's process may be a wrapper shell with the agent as its child | refuted: `agent_env.main` calls `os.execvpe` (`src/lado/agent_env.py:394`), the pane's pid is the CLI | — | dropped |
| F5 | 2 | external 4 | EPERM counts as ended | refuted: the safe side, a pid reused by another user's process | — | dropped |
| F6 | 2 | external 5 | the `ps` timeout is per call, so a hung `ps` stretches the wait past 10 s | confirmed | minor | declined: a hung `ps` is not a real case; the wait stays bounded |
| F7 | 2 | external 6 | the unit test relies on `AGENTS_TIMEOUT` = 10 against a 1 s hangup delay | confirmed | minor | declined: a tenfold margin |

Metrics: 3 local rounds, 1 external, 0 substitutes. Confirmed 5 (local 2, external 3),
refuted 2 (external). Fixed 1 (F2); declined 4, all minor. Findings in code changed by the
developer's cleanup: 0.

## Checks

- Round 1: `make lint` green; `make test` 3620 passed, 1 skipped;
  `uv run pytest -m integration -n auto tests/integration/test_uninstall_process.py
  tests/integration/test_agent_terminal.py` 16 passed; `openspec validate
  uninstall-waits-for-agents --strict` and `--specs --strict` valid. Able to fail: without
  the wait two unit tests and the integration test fail (3 of 3), without the zombie check
  the zombie unit test fails; on `41e2259` without the wait 3 of 3 red, with it 5 of 5
  green.
- Round 3: trial archive, `openspec validate --specs --strict` 43 of 43.
- CI on `7897acb` (run 39669395878): 23 of 23 green, `ci-ok` and smoke 8 of 8.
- Round 4: `openspec validate --specs --strict` 45 of 45; CI on `c468030`: 23 of 23
  green, smoke 8 of 8.

## Not checked

- Whether the real Claude Code (and other CLIs) waits for its session-end hook to end
  before exiting; a hook that outlives the agent's process is not covered by the wait.
  Only a live test catches it, run with the human's yes.
- The agents' child processes (`lado mcp`) are not waited for.
- `make check` and `make test-integration` as a whole were not run locally; CI ran them.

## Found on the way

None.
