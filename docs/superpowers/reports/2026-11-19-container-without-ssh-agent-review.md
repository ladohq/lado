# LAD-300 container-without-ssh-agent: review report

Pull request #340 `feature/lad-300-container-without-ssh-agent` → `main`. Scale: full.
Head reviewed: `b26f161f`. LADO's container no longer mounts the host's ssh agent: the
socket bind, its helper, sudo rule, profile and the image's `ssh_known_hosts` are gone,
the installer no longer asks for or writes `LADO_SSH_AGENT`, and a line of it left in
`.env` is named loudly as set but not used. Git in the container goes over https with the
tokens of Settings → Git servers; cloning an ssh address of a host not saved there leads
to adding that server. The Add form starts with an empty address and a placeholder; the
GitHub token hint names `repo`.

## Rounds

1. Local, a full pass over `origin/main...748a0769`: spec, tests, silent failures,
   comments, types, general, and the architecture against AGENTS.md. Found F1
   (important) and F2 (minor).
2. Local, precision on the delta `748a0769..b26f161f`. F1 and F2 resolved; new F3
   (minor). External 1, Claude Code GitHub Action: no blocker; every risky file
   (`clone.py`, `install.sh`, `entrypoint.sh`, `Dockerfile`, `compose.yaml`,
   `GitServers.tsx`) read; docs, specs and tests not read (covered locally).

External rounds used: 1 of 2. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | the session-clone spec promised "no ssh key for <host>" and Add for any port-22 ssh address of an unsaved host, while the code gives it only to the user `git` | fixed in `77a876bc`: both requirements rewritten |
| F2 | minor | long lines in `docker/Dockerfile`, `docs/design/ui.md`, `docs/design/modules.md` | fixed in `b26f161f` |
| F3 | minor | a 152-character line in the session-clone delta, short leftovers of a rewrap in `modules.md` | declined: source look only, rendering unchanged |
| E1 | minor | "no ssh key" is inexact when a user put a key into the volume's `~/.ssh` by hand | declined: LADO offers no such path (design D1) |
| E2 | — | the living container spec still describes the `LADO_SSH_AGENT` bind | refuted: the delta removes it at archive; trial archive green |
| E3 | — | `docs/research/*` and `docs/epics/*` mention the ssh agent | refuted: historical notes; the epic's files are not this change's |

## Metrics

- Rounds: 2 local, 1 external, 0 stand-ins.
- Confirmed: local 3 (1 important, 2 minor), external 1 (minor).
- Refuted: local 0, external 2.
- Findings in code changed by fixes: 0.

## Checks

- Round 1: `make lint` clean; `make test` 5878 passed, 14 skipped;
  `openspec validate container-without-ssh-agent --strict` valid; trial archive and
  `openspec validate --specs --strict` 87/87.
- Round 2: trial archive and `validate --specs --strict` 87/87.
- CI at `b26f161f`: 27/27 successful, `ci-ok` green (`ui (3)` once red before the fixes
  on the known flake LAD-298).
- Not run locally: `make test-container` (green in CI on amd64 and arm64), UI and
  integration re-runs in review (run by the developer and CI), `make test-live`.

## Found on the way

- None.

## Residual risk

- A real ssh from the container to an unsaved host without known_hosts (expected
  `Host key verification failed`, kind `host_key`) is covered by unit tests of the texts
  only; the manual check's step 8 covers it.
- The manual check in Docker (steps 0–10: update from 0.47.0, the GitHub login taken over,
  clone, push and pull request over `git@github.com:`, rollback) is left to the human.
- `install.ps1` on Windows not run: unchanged, it runs `install.sh`.
- No change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py`
  or `tests/live/`: live tests not needed.
