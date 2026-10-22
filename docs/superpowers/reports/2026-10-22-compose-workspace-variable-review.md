# LAD-124 compose-workspace-variable: review report

Pull request #136 `fix/lad-124-compose-workspace-variable` → `main`. Scale: tweak,
reviewed by precision; compose read by its behaviour. Head reviewed last: `1f40b22`
(= the remote head). In `runtime.py` only the mise paragraph of `CONTAINER_INSTRUCTIONS`
and one docstring changed; `providers/`, `hooks.py`, `mcp_server.py`, `agent_env.py` and
`tests/live/` did not change.

## Rounds

- **Round 1, local** (`origin/main...324c30e`), with a trial archive in a scratch copy:
  F1, F2, F3.
- **Round 2, local** (precision over `324c30e..1f40b22`): F1 and F2 resolved, no new
  findings.
- **Round 1, external** (Claude Code GitHub Action; request comment 6327030680, answer
  newer than it; reply with the triage 6327093851): no blockers, four minor (E1-E4). It
  is of the same model family, so its "nothing more" weighs less.

External rounds used: 1 of 1.

## Who read which area

| Area | Local round 1 | Local round 2 (delta) | External round 1 |
|---|---|---|---|
| compose (`docker/`) | whole | the header | `docker/compose.yaml` |
| documents (README, CHANGELOG, `docs/`) | whole | install, README, CHANGELOG | `docs/install.md`, CHANGELOG only |
| specs (the `container` delta, proposal, tasks) | whole, plus the trial archive | `tasks.md` | not opened |
| tests | `tests/test_docker.py`, `tests/container/*` | the new unit test | `tests/test_docker.py` only; `tests/container/` not opened |

The external reviewer read files at HEAD on a shallow checkout, without the diff against
`origin/main`.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (general, docs) | the guide does not make the workspace folder, and compose no longer makes it (`create_host_path: false`): a new install without `~/workspace` fails at `up -d`; troubleshooting knew the error only for the placeholder path | confirmed | important | fixed in `1f40b22` (`mkdir -p ~/workspace`, a troubleshooting line for any path, CHANGELOG); test `test_the_guide_makes_the_workspace_before_compose_needs_it` seen red |
| F2 | 1 | local (comments) | the PR description named CI of the older head, and its manual check's grep also printed the secrets and ssh-agent binds | confirmed | minor | fixed in the PR description |
| F3 | 1 | local (general) | Docker Desktop (macOS) may word the refusal for a missing bind source otherwise than `bind source path does not exist` | unverifiable | — | residual risk: the troubleshooting line says the wording may differ while the path is the same; step 5 of the PR's manual check, on a Mac |
| E1 | ext 1 | external | CHANGELOG should say an installed `.env` whose folder is gone fails on update | confirmed | minor | declined: the line already says a missing workspace is no longer made and `up -d` refuses |
| E2 | ext 1 | external | `docker/compose.yaml:6` is now about 100 columns | refuted: 98 columns, shorter than on `main` | — | dropped |
| E3 | ext 1 | external | the bind's comment could name LAD-73 | confirmed | minor | declined: the reason is in the docstring of `test_compose_mounts_the_workspace_at_the_hosts_own_path`, which guards the expression |
| E4 | ext 1 | external | Docker Desktop's wording unverified | = F3 | — | merged into F3 |

Metrics: 2 local rounds, 1 external, 0 substitutes. Local confirmed 2 (F1, F2), refuted
0; external confirmed 2 (E1, E3), refuted 1 (E2); unverifiable 1 (F3, with E4). Findings
in code changed by the developer's cleanup: 0.

## Checks

- `make lint` green on `1f40b22`; `tests/test_docker.py`: 92 passed, 1 skipped. The
  developer reported `make test` on `1f40b22`: 3688 passed, 1 skipped (3687 on `324c30e`,
  rerun by the reviewer).
- `openspec validate --specs --strict`: 44 of 44 after the archive.
- Grep of `LADO_PROJECTS` and of "project" for the human's repository: clean outside the
  historical documents.
- CI 23 of 23 on `1f40b22`, container amd64/arm64 and all 8 smoke cells included. On
  `324c30e` two macOS smoke jobs got no runner ("not acquired by Runner of type hosted");
  rerun once, they passed on the new head: an infrastructure flake, no test involved.

## Not checked

- F3: Docker Desktop's exact refusal on macOS.
- The container tests ran only in CI on Linux; neither the developer nor the reviewer had
  Docker.
- The external round did not read the `container` delta, `tasks.md` or `tests/container/`.
