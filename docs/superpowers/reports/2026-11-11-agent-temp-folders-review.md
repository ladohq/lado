# LAD-247 agent-temp-folders: review report

Pull request #284 `hotfix/lad-247-agent-temp-folders` → `main`. Scale: hotfix, depth precision
(round 1 widened to breadth: the diff touches `runtime.py` and `providers/`). Head reviewed:
`a167ec44`. Each agent LADO launches gets a temporary folder of its own,
`<parent>/lado-<uid>/<session>/<agent>` (0700), as `TMPDIR` for every provider and as
`CLAUDE_CODE_TMPDIR` for Claude Code, and every agent's instructions say to keep temporary
files there. Delta: `agent-variables` (four requirements added, one modified).

## Rounds

1. Local, breadth, `origin/main...b92d5d66`: F1, F2.
2. Local, precision, `b92d5d66..a167ec44`: the F1 fix holds, no new findings. Then external 1
   (Claude Code GitHub Action): E1–E5; it read every changed source file, not the tests,
   documents and openspec.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | with the login shell (the default), a worker an agent's `lado mcp` spawns got its folder inside its spawner's: the shell was started with the spawner's `TMPDIR` | fixed in `27713870` (the shell starts without LADO's launch variables), docs in `a167ec44` |
| F2 | minor | a failed `git worktree add` after the folder is made leaves an empty folder and its record | declined: reused by a spawn of the same name, removed by `lado forget` |
| E1 | minor | when the user's `TMPDIR` changes between launches, the old folder is no longer removed | declined: the system cleans its tmp |
| E2 | — | a worker spawned through `lado mcp` loses the macOS `/var/folders/…/T/` parent | refuted: decision D3, documented |
| E3 | — | on macOS a long `$TMPDIR` may exceed the ~104-byte Unix socket path limit | unverifiable without macOS; residual risk |
| E4 | minor | a relative `TMPDIR` gives a folder that depends on the cwd | declined: a relative `TMPDIR` is wrong for any program |
| E5 | — | Codex under its sandbox and the live test not run | residual risk, see Not checked |

## Found on the way

- None.

## Checks

On `a167ec44`:
- `make lint`: exit 0.
- Unit: `tests/test_agent_env.py`, `tests/test_temp_dirs.py`: 110 passed (round 1:
  `test_temp_dirs.py`, `test_runtime.py`: 649 passed).
- Integration: `test_login_shell.py`, `test_agent_temp_folders.py`: 3 passed, 1 skipped (an
  older test: this system's `/etc/profile` sets `PATH`).
- CI: 27 pass, `ci-ok` green, the pull request `CLEAN`.
- At archive: `openspec validate --specs --strict` 82 passed.

## Not checked

- The live test `tests/live/test_live.py::test_an_agent_s_shell_has_its_own_temporary_folder`:
  written, not run (paid models).
- Codex writing to `$TMPDIR` under its own sandbox on macOS (task 3.2): bwrap does not start in
  LADO's container.
- E3, the socket path length on macOS. A probe in an agent's window there:
  `python3 -c "import socket,os;s=socket.socket(socket.AF_UNIX);s.bind(os.path.join(os.environ['TMPDIR'],'x'*20+'.sock'))"`.
- The full unit and integration suites were not run locally; CI ran them.
