# LAD-107 agent-base-tools: review report

Pull request #106 `fix/lad-107-agent-base-tools` → `main`. Scale: tweak, reviewed for
precision, but round 1 read the whole diff, as it changes the ownership of the Python LADO
runs on and every agent's `PATH`. Head reviewed last: `17d5c15` (= the remote head).
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
are not changed: no live tests needed.

## Rounds

- **Round 1, local** (the whole pull request against `origin/main`, head `17d5c15`;
  lenses spec, tests, comments, general): F1.
- **Round 1, external** (Claude Code GitHub Action, request
  https://github.com/ladohq/lado/pull/106#issuecomment-6262301662, answer 6262305957,
  "Claude finished"): E1-E5.

No second external round: the cap of 1 for a tweak was used. The external reviewer is of
the same model family, so its "nothing blocking" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | The comment line before LADO's `uv tool install` (~105 characters) runs past the file's wrap (~92), `docker/Dockerfile:151` | confirmed | minor | declined: fix at the next touch of the file |
| E1 | 1 | external | The requirement "The image tells the agents they run in a container" is one long sentence that could read as if npm's prefix and the variables were on `PATH` | confirmed | minor | declined: the living spec had the same shape before, and the parentheses make it unambiguous |
| E2 | 1 | external | Task 1.2 does not say whether `uv tool install` finds the Python or is given its path | refuted | — | the build report and the PR description say it finds it; the Dockerfile passes no path (`docker/Dockerfile:154-155`) |
| E3 | 1 | external | Task 4.1 is checked though 2 tests fail on a local Python 3.15 | refuted | — | green on 3.13 and in CI (3.10, 3.13); the two clone tests fail on `main` too on Python 3.14+, recorded in BACKLOG.md (a92ead8) |
| E4 | 1 | external | A future apt package could bring Debian's `/usr/bin/python3` and shadow the fallback | refuted as a defect | — | no package of the list depends on python3 with `--no-install-recommends`; the container test `python3 --version` → `3.13.` would fail (`tests/container/test_toolchains.py:274`) |
| E5 | 1 | external | `find /opt/uv/python ! -user root \| head -1` passes vacuously if the folder is missing | refuted | — | the next check's `readlink -f` requires `/opt/uv/python/cpython-3.13.`, and the neighbouring test answers 3.13 (`tests/container/test_toolchains.py:292-294`) |

No fixing commits.

## Spec check

- **The image carries the agents' base tools**: `docker/Dockerfile:71`; unit
  `test_the_image_carries_the_agents_base_tools` with a negative test naming a missing
  package; container `test_the_base_tools_and_openspec_answer_on_a_clean_home`, its
  package keys shared with the unit test.
- **The image carries openspec at its pin**: `ARG` and its own `RUN` after the CLIs; unit
  tests for the pin and a loose pin (negative), `/opt/tools` named in exactly three
  places; container: the pin, `command -v`, mise's 1.14.0 does not shadow it, the two
  variables in a login shell and in `docker exec`.
- **The image's python3 gives way to a project's Python**: installed as root before
  `USER lado`, `chown` only on `/opt/uv/tools` and `/opt/uv/bin`, `/opt/fallback/bin` last
  on `PATH` in `ENV` and `profile.sh` (unit); container: 3.13 outside a project, 3.12 in
  one and 3.13 above it, pip refused, files root's and not writable, venv works,
  `lado --version` answers.
- **The image tells the agents they run in a container** (modified): all three earlier
  scenarios kept, the new `PATH`, the openspec variables and their scenario added.
- Every task of `tasks.md` is checked but 2.4 (image size), which says why: the
  developer's container has no Docker.

## Checks

- `make lint`: green.
- `tests/test_docker.py` on Python 3.13: 90 passed, 1 skipped.
- `openspec validate agent-base-tools --strict`: valid; `openspec validate --specs`: 39
  passed.
- CI run 39217387050 on `17d5c15`: success, every job, container amd64 and arm64, smoke ×8
  included.

## Not checked (residual risk)

- The image's size before and after (D6, task 2.4): no Docker in the agents' container;
  step 1 of the human's check in the PR description.
- An sdlc session starting on a new home volume (second half of AC-2): the human's check.
- Container tests were not run locally; CI's container cells prove them.
- `/opt/uv/tools` (LADO's environment) stays writable by `lado`: an agent can change
  LADO's packages, though not the interpreter. Out of scope by design ("Making the rest of
  `/opt` root's").

## Found on the way

Nothing new; the clone defect on Python 3.14+ is already in BACKLOG.md (a92ead8).
