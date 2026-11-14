## 1. The rule

- [ ] 1.1 `src/lado/runtime.py`: in `WORKER_INSTRUCTIONS` and `RUN_WORKER_INSTRUCTIONS` replace
  "Commit your work on that branch." with the sentence of
  the proposal, one shared constant (e.g. `COMMIT_RULE`) used by both so they cannot drift.
  Check: a unit test in `tests/test_runtime.py`: the spawned worker's prompt (claude, as
  `test_every_worker_is_told_the_human_reply_rule`) and a flow run worker's prompt both hold
  the sentence; `make test`.

## 2. Live test

- [ ] 2.1 `tests/live/test_live.py`: a new test `test_a_worker_commits_unless_its_task_says_not_to`,
  in the shape of `test_an_agent_s_shell_has_its_own_temporary_folder`: one session, two
  workers, w1 with the task of the scenario "The task forbids the commit", w2 with that of
  "The task says nothing of commits"; wait for both reports; assert w1's branch has no commit
  beyond the session's HEAD and `hello.txt` is in its worktree, untracked, and w2's branch has
  a commit holding `hello.txt`; `check_supervisor_kept_still()`, stop the session. Runs for
  every provider of `live.yml` (Codex and Claude Code among them). Check: it collects
  (`uv run pytest -m live --collect-only tests/live/test_live.py`); written, not run (paid):
  the build report says so.

## 3. Docs and CHANGELOG

- [ ] 3.1 `docs/design/agents.md`: where a worker's instructions are described, the rule on
  commits and its exception.
- [ ] 3.2 CHANGELOG.md under `## 0.47.0 (unreleased)`, Fixed: a worker no longer commits when
  its task tells it not to.

## 4. Checks

- [ ] 4.1 `make lint`, `make test`, `openspec validate worker-commit-follows-task --strict`,
  `openspec validate --specs --strict` and the trial archive of the settings' Checks.
