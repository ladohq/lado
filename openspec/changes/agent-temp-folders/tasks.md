## 1. The folder (core)

- [x] 1.1 Unit, failing first: the folder's path from a parent (`tmp_path`) and from no `TMPDIR`
  (`/tmp`), made with mode 0700 at each level, made again when deleted; `lado-<uid>` as a link,
  a file or another owner's folder (owner faked) refused with the line of D2; removed by
  `remove_agent_state` and, with the session's folder, by `remove_session_state`. Then the code
  by D1, D2, D5 (in `providers/base.py` beside `state_path`, or `agent_env.py`).
- [x] 1.2 Unit, failing first: the launch environment (`_launch_env`, through the launch of
  the start, the resume and `spawn_worker`) of the providers `claude`, `codex`, `kilo` and
  `opencode` has `TMPDIR` = the agent's folder, listed in `LADO_LAUNCH_VARS`; two workers of
  one session differ; a login shell's `TMPDIR` and a project's `TMPDIR` become the parent and
  `_layer_warnings` names neither (D3, D6). Then `AgentSpec.temp_dir` and the code.
- [x] 1.3 Unit (`tests/test_claude.py`), failing first: Claude Code's `Launch.env` has
  `CLAUDE_CODE_TMPDIR` = `spec.temp_dir` (D4); the other three providers set no variable of
  their own for it. Then `providers/claude.py`.
- [x] 1.4 Unit, failing first: the instructions of a supervisor, a worker, a run's worker and a
  read-only worker, in and out of the container, hold the line of D7 after `MESSAGING`. Then the
  constant in `runtime.py`.

## 2. Across processes (integration, fake agent)

- [x] 2.1 `tests/integration/` (marker `integration`): a session with two workers on the fake
  agent; each runs `sh` writing `$TMPDIR` and `touch $TMPDIR/pr.md` to a file in its folder; the
  two folders differ, exist, are 0700, lie under the test's parent (its own `TMPDIR`, never the
  real `/tmp`), and each `pr.md` is in its own. `finish_worker` of one removes its folder and
  leaves the other's. A run's worker's file survives `lado stop` and the resume.

## 3. Real CLIs (live)

- [x] 3.1 `tests/live/test_live.py`: an agent asked to run `echo "$TMPDIR"` in its shell and
  report it; the value is its folder `…/lado-<uid>/<session>/<agent>`; every provider of
  `live_provider` (Claude Code and Codex at least). Written, not run in a normal round; the
  build report says so.
- [ ] 3.2 By hand, named in the build report: a Claude Code worker's scratchpad (its system
  prompt's "Scratchpad directory") lies inside its folder; a Codex worker writes to `$TMPDIR`
  without an approval prompt on a host where its sandbox runs (macOS).
  Not done in full: built in LADO's Linux container. Claude Code 2.1.295 made its own
  temporary root (`claude-<uid>/<cwd>/<session>/`, where the scratchpad is) inside the
  `CLAUDE_CODE_TMPDIR` it was given, and nothing in `/tmp/claude-<uid>`; Codex 0.162.0's
  sandbox (bwrap) cannot start in the container, so its write under the sandbox waits for a
  check on macOS.

## 4. Documents and regression

- [x] 4.1 `docs/design/agents.md`, the agent's environment: the temporary folder, its parent,
  its lifetime, Claude's `CLAUDE_CODE_TMPDIR`, and that it is no security boundary. The
  docstring of the module that makes the folder says the same in short.
- [x] 4.2 CHANGELOG.md, `## 0.46.1 (unreleased)` (add it on top), Fixed: each agent has a
  temporary folder of its own, so two agents' drafts no longer overwrite each other (LAD-247).
- [x] 4.3 Regression: `make lint`, `make test`, `uv run pytest -m integration -n auto` on the
  changed and added files of `tests/integration/` and on `tests/integration/test_agents.py`,
  `test_outside_variables.py`, `test_project_variables.py`, `test_read_only.py`,
  `test_container_sessions.py`; `openspec validate agent-temp-folders --strict` and the trial
  archive of the settings' Checks.
