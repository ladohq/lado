# LAD-164 docker-installer: review report

Pull request #187 `feature/lad-164-docker-installer` → `main`. Scale: full.
Head reviewed last: `38c0570d` (= the remote head), with `origin/main` (LAD-163,
providers-section-and-start-screens) merged in at `11bfeb98` without conflicts. One
command installs or updates LADO's container: `install.sh` for macOS, Linux and WSL2, and
`install.ps1`, which runs it in Ubuntu inside WSL on Windows; both ship with each GitHub
release, stamped with its version. `providers/`, `hooks.py`, `mcp_server.py`,
`runtime.py`, `agent_env.py` and `tests/live/` did not change: no live tests needed.

## Rounds

- **Round 1** (`origin/main...31e711b7`): a local pass in breadth with every lens but
  types (no new types) and the architecture against AGENTS.md. F1-F4 found.
- **Round 2** (`31e711b7..1590a546`): a local precision pass over the fixes of F1-F4; no
  new findings. External 1 of 2 (Claude Code GitHub Action) over the whole pull request:
  E1-E7.
- **Round 3** (`1590a546..38c0570d`), after the first archive failed strict validation
  (two modified `container` requirements over 500 characters, a placeholder Purpose of the
  new capability): the requirements shortened with their rules kept, the details moved
  into two new scenarios that `tests/test_docker.py` checks; `## Purpose` added; main
  merged; AGENTS.md's `docker/` line made one line again. G1 found. External 2 of 2 over
  the delta: no defects, G1 found independently.

External rounds used: 2 of 2. The external reviewer is of the same model family as the
kit's agents, so its "no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | `install.ps1` under `irm \| iex` left strict mode, `$ErrorActionPreference='Stop'` and its functions in the human's PowerShell | fixed in `1590a546` (all but `param` runs in `& { … }`), test `test_iex_leaves_the_humans_powershell_as_it_was` |
| F2 | important | `--image` was silently ignored on a rerun | fixed in `1590a546` (`rewrite_env` writes `LADO_IMAGE`), tests `test_image_on_a_rerun_*` |
| F3 | minor | `--dir ~/lado-docker/` with a trailing slash made a second LADO (`lado-lado-docker`) | fixed in `1590a546`, test `test_a_trailing_slash_is_still_the_default_folder` |
| F4 | minor | In WSL without `docker` the script named only Docker Desktop, not its WSL integration | fixed in `1590a546`, test `test_no_docker_in_wsl_names_docker_desktop_and_its_wsl_integration` |
| G1 | minor | AGENTS.md's shortened `docker/` line lost "profile" (`docker/profile.sh` exists) | declined: the map is not a full list (`docs/design/modules.md` is), and AGENTS.md is at its 200-line limit |
| E1 | — | external: `param` not bound under `iex`, strict mode throws | refuted on pwsh 7.4.6; Windows PowerShell 5.1 unverifiable here |
| E2, E6, E7 | — | external: `exit` ends a caller's script; `--dir .` gives an invalid compose name; `latest` and RC tags | refuted (the caller goes on; `lado--` is a valid name; RCs are pre-releases, tags by PEP 440) |
| E3, E5 | minor | external: `-Yes` never installs Ubuntu; the ssh agent outside Docker Desktop and the port checked on 127.0.0.1 only | declined: `-Yes` takes the defaults, and the question's is no; design D5 |
| E4 | — | external: a fresh, never opened Ubuntu may blame WSL integration | unverifiable without Windows: residual risk |

## Checks

- Local on `38c0570d`: `make lint` green; `make test` 4625 passed, 7 skipped (5 of them
  pwsh tests: no pwsh on PATH); `openspec validate docker-installer --strict` valid;
  a trial archive then `openspec validate --specs --strict` 53 passed, 0 failed.
- CI on `38c0570d`: all 23 jobs green (unit, integration ×6, ui ×2, js, container
  amd64/arm64, smoke ×8); the pwsh tests ran there.

## Not verified

- `install.ps1` under Windows PowerShell 5.1 and on a real Windows (E1 on 5.1, E4, the
  questions through WSL's console, the link in Windows' browser, the mDNS name and the
  firewall for the phone): the human's manual check at the RC (docs/release.md 4.5).
- A Mac with Docker Desktop: the manual check at the RC; colima, OrbStack and Docker
  Desktop on Linux are outside the design.
- `tests/container/test_install.py`, `make test-integration` and `make check` were not
  run locally; CI ran them, all green.

## Found on the way

- AGENTS.md is now exactly 200 lines, the limit of `tests/test_agents_md.py`: the next line
  any task adds to the map breaks the test.
