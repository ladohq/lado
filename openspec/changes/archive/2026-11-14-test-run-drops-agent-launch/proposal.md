Task: LAD-282

## Why

`make test` run by a LADO agent (in LADO's image, or any agent's shell) is red where CI is
green: `tests/test_temp_dirs.py::test_the_users_tmpdir_is_the_parent_and_not_warned_of[shell]`
fails, and with only `LADO_LAUNCH_VARS` cleared by hand
`test_each_agent_has_a_tmpdir_of_its_own[codex|kilo|opencode]` fails too. On a clean `main`
(d4b68a82) the same; `env -u LADO_LAUNCH_VARS -u CLAUDE_CODE_TMPDIR make test` is green
(6124 passed, 7 skipped). Every developer and reviewer working in LADO sees a false red and
must find out it is not theirs.

The cause: a launch sets on top of an agent's environment the variables it names in
`LADO_LAUNCH_VARS` (here `CLAUDE_CODE_TMPDIR,LADO_AGENT,LADO_ENV_DIR,LADO_HOME,LADO_REPOS,
LADO_SESSION,LADO_TMUX_SOCKET,TMPDIR`; a model server's agent also its key and config
variables). `tests/conftest.py` clears a fixed list of LADO's own names, but neither
`LADO_LAUNCH_VARS` nor `CLAUDE_CODE_TMPDIR` is on it. The test run's environment reaches
the agents the tests start (`LADO_AGENT_ENV=inherit`), so:

- `agent_env.without_launch` drops from it every name `LADO_LAUNCH_VARS` lists, `TMPDIR`
  among them: the `TMPDIR` a test set as "the user's" is dropped, and the `[shell]` case
  sees none;
- a non-Claude agent inherits the outer agent's `CLAUDE_CODE_TMPDIR`, which only a Claude
  agent may have.

The fixed list was written before LAD-247 added the launch's own variables; every new
launch variable would leak again the same way.

## Options

1. **Clear what the launch named** (chosen): `tests/conftest.py` clears
   `LADO_LAUNCH_VARS` and every name it lists, except `TMPDIR`, besides its fixed list.
   Long-term cost: none; a launch variable added later is cleared without touching
   conftest (one source of truth: the launch's own list).
2. **Add the two names to the fixed list** (the task's proposal): fixes today's red, but
   the next variable a launch sets (a provider's own root, a model server's key) leaks
   again and is found the same way, by a false red.
3. **Run `make test` under `env -u …`** in the Makefile: hides the cause from a plain
   `uv run pytest` and puts agent names into the Makefile.

## What Changes

- `tests/agent_helpers.py`: a function that gives the environment of a test run started
  in an agent's shell: without LADO's fixed names (the list now in conftest), without
  `LADO_LAUNCH_VARS` and every name it lists, but `TMPDIR`.
- `tests/conftest.py`: clears the environment through that function instead of its own
  loop; its comment says why the launch's names go and `TMPDIR` stays.
- `tests/test_agent_helpers.py` (or the module that tests `agent_helpers`): a unit test of
  the function on an agent-like environment.
- `docs/testing.md`: the sentence on what `tests/conftest.py` clears names the launch's
  variables.

## Acceptance criteria

- AC-1: In an agent's shell of LADO (`LADO_LAUNCH_VARS` and `CLAUDE_CODE_TMPDIR` set),
  `uv run pytest -n0 tests/test_temp_dirs.py` passes, and `make test` passes with no
  `env -u`.
- AC-2: A unit test gives the function an environment with `LADO_LAUNCH_VARS` listing
  `CLAUDE_CODE_TMPDIR`, `TMPDIR` and a model server's key variable, and LADO's fixed names
  set: the result keeps `TMPDIR` and the variables no list names, and holds none of the
  others nor `LADO_LAUNCH_VARS`.
- AC-3: Without `LADO_LAUNCH_VARS` (CI), the test run's environment is as before: the same
  fixed names cleared, nothing else.

## Scope

- `tests/conftest.py`, `tests/agent_helpers.py`, a unit test of the helper,
  `docs/testing.md`.

## Out of scope

- LADO's code (`agent_env`, the launch): it behaves as designed; only the test run's
  isolation is wrong.
- Clearing `TMPDIR`: the agent's own temporary folder is where the run's `tmp_path` belongs
  (sdlc: agents keep temporary files in their own `TMPDIR`), and the autouse `agents_tmp`
  gives each test its own `TMPDIR` anyway.
- A CHANGELOG line and a version bump: nothing LADO's users see changes (tests only).

## Impact

- Tests only; no code of LADO, no schema, no MCP tool or CLI change: neither a minor nor a
  patch bump of its own, no CHANGELOG line.
- No behaviour rule changes: no delta; archived with `--skip-specs`.
