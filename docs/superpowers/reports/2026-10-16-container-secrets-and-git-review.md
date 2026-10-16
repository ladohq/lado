# LAD-76 container-secrets-and-git: review report

Pull request #76 `feature/lad-76-container-secrets-git` → `main`. Scale: full, reviewed
breadth first. Head reviewed last: `42ea08c` (= the remote head). `src/lado/runtime.py`,
`src/lado/agent_env.py` and `src/lado/providers/base.py` changed: every agent now gets
`LADO_ENV_DIR` when it is set, so the human may want live tests before the merge; they
were not run.

## Rounds

- **Round 1, local** (breadth over `origin/main...3bb0071`; passes: spec, tests, silent
  failures, comments and descriptions, general and security, architecture): F1
  (important), F2, F3 (minor), U1 (unverifiable). CI green on `3bb0071`. Sent back to the
  developer.
- **Round 2, local** (precision over the delta `3bb0071..42ea08c`): the fix of F1 in
  `providers/base.py` checked (the import `providers/base → agent_env` is allowed, an
  empty value is not passed, `mcp_server(...).env` gets the variable too). `make lint`
  exit 0; unit `test_providers`, `test_lazy_imports`, `test_agent_env`, `test_runtime`
  under `-n auto`: 693 passed, 1 failed (`test_agent_env.py::test_a_slow_shell_times_out`,
  passed when rerun alone with `-n0`: a flake, older than the PR). CI green on `42ea08c`
  (run 38819965521). No new findings.
- **Round 1, external** (Claude Code GitHub Action over `origin/main..42ea08c`, request
  22:58:17Z, "Claude finished" 22:59:32Z): nothing blocking; it confirmed F3 and U1 and
  found E1–E3 (minor). The external reviewer is of the same model family, so its "nothing
  blocking" weighs less.

External rounds used: 1 of 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (spec, tests) | outside a container a worker that the supervisor's `lado mcp` launches (`spawn_worker`, `start_session`) did not get the folder's variables: `LADO_ENV_DIR` was not passed to the agent; the integration test hid it by running with `LADO_AGENT_ENV=inherit` | confirmed | important | fixed in `42ea08c`: `providers.agent_env` passes `LADO_ENV_DIR` when set and not empty; `tests/test_providers.py::test_lado_passes_its_outside_folder_on_to_each_agent` |
| F2 | 1 | local (PR body) | step 2 of the manual check switched the branch of the human's checkout | confirmed | minor | fixed in the PR body: `git worktree add`, then `git worktree remove` |
| F3 | 1 | local | the folder is read twice per launch, so a warning's text can differ from what the agent got | confirmed | minor | declined: a window of milliseconds, only a warning's text is at stake |
| E1 | ext 1 | external | `doctor.check_outside` relies on the text of `agent_env.outside`'s lines | confirmed | minor | declined: a unit test pins the wording, so a change fails loudly |
| E2 | ext 1 | external | on Linux a host socket of root's, after the `chown` in the container, is `lado`'s uid on the host too (same inode) | confirmed | minor | declined: the human passes that socket through `LADO_SSH_AGENT`, and the headers say every agent of the container gets the host's keys |
| E3 | ext 1 | external | a git name or email removed from `.env` stays in the global config on the volume, and the "no identity" warning no longer shows | confirmed | minor | declined: an empty value is skipped on purpose; a changed value works as the header says |

## Not verified (residual risk)

- U1: the real Docker Desktop ssh socket `/run/host-services/ssh-auth.sock` through
  compose's long bind form with `create_host_path: false`, and its `chown` with a second
  LADO of another uid. The tests use a sidecar container's socket. Covered only by the
  PR's manual check on a Mac, steps 4, 9 and 11; should compose refuse the path, the
  fallback is the short `-v` form for that bind.
- `make test-container` was not run locally after `42ea08c` (the fix does not change the
  image); CI's `container` job is green on `42ea08c` on amd64 and arm64.
- Live tests (`make test-live`) were not run.
- Flake: `tests/test_agent_env.py::test_a_slow_shell_times_out` (0.5 s timeout under
  `-n auto`), seen by the developer and the reviewer.

## Metrics

Rounds: 2 local, 1 external. Confirmed: 3 local (F1–F3), 3 external (E1–E3); refuted: 0;
unverifiable: 1 (U1). Findings in code the developer's cleanup changed: 0.

## Found on the way

None.
