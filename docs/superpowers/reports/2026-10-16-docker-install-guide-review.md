# LAD-83 docker-install-guide: review report

Pull request #82 `fix/lad-83-docker-install` → `main`. Scale: tweak, reviewed for
precision. Head reviewed: `fa3a757` (= the remote head, `origin/main` in it). The change
touches `runtime.py` (the warning's rule) and `docker/entrypoint.sh` (the server's ssh
agent), not `providers/`, `hooks.py`, `mcp_server.py`, `agent_env.py` or `tests/live/`:
no live tests needed. The human checked the pull request by hand twice.

## Rounds

- **Round 1, local** (`ffa5ae7`): F1–F3.
- **Round 2, external** (`10eb181`, 1 of 1): E1–E3, all refuted.
- **Round 3** (`1843117`): M1, declined.
- **Round 4** (`90ac8e4`): M2, declined; the human asked for its fix.
- **Round 5** (`f6c47cb`): M2 fixed.
- **Round 6** (`d7f7f0d`): the update for both ways of install; nothing new.
- **Round 7** (`fa3a757`, back from `merge_ok` after the human's check by hand 1): the
  delta `d7f7f0d..fa3a757` fixed H1–H5, nothing new; then the human's check by hand 2
  (from scratch, on `fa3a757`): 10 of 10 steps passed, H1–H5 confirmed by hand;
  observation A became M3 (declined), B was refuted.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (checks, CI) | The pull request conflicted with `main`; CI did not run | confirmed | blocker | fixed in `ed33deb` |
| F2 | 1 | local (silent failures) | `outside_repos` answered 500 in a container on a symbolic link loop | confirmed | important | fixed in `06ccb3f`, with a test |
| F3 | 1 | local (spec) | The spec's scenario about `prune` was wider than its test | confirmed | important | fixed in `10eb181` |
| E1–E3 | 2 | external | A note in modules.md; a call on every check; checking known_hosts against fingerprints | refuted | — | dropped: the line exists / not a defect / decision D4 |
| M1 | 3 | local (texts) | README's short start lacks `env \| grep` / `unset` | confirmed | minor | declined: that advice is the first step of the full section; left to the human |
| M2 | 4 | local (texts) | "mounted" in the paragraph about doctor | confirmed | minor | fixed in `f6c47cb` (the human's decision) |
| H1 | 7 | check by hand 1 | The server in a container had no `SSH_AUTH_SOCK`: Clone from URL over ssh failed | confirmed | important | fixed in `d370955`, `fa3a757`; confirmed by hand in check 2 |
| H2 | 7 | check by hand 1 | The pull request's `known_hosts` check expanded `~` on the host | confirmed | minor | fixed in the pull request's description |
| H3 | 7 | check by hand 1 | `unset` did not match the `grep` | confirmed | minor | fixed in `2fc9321`, `9fbcb8e` |
| H4 | 7 | check by hand 1 | Version numbers in examples go stale | confirmed | minor | fixed in `2fc9321` |
| H5 | 7 | check by hand 1 | The volume filter matched a substring | confirmed | minor | fixed in `2fc9321` (`^<project>_home$`) |
| M3 | 7 | check by hand 2, A | *Your first session* does not say that Claude Code in a container asks to trust each new folder unless its mode is `bypassPermissions` | confirmed | minor | declined (last round's minor; LADO shows the wait under Needs you); left to the human |
| B | 7 | check by hand 2, B | `docker compose exec lado sh -c` gets no `SSH_AUTH_SOCK` | refuted | — | dropped: no login shell, by design; nothing in the guide or the pull request runs ssh with a key under `sh -c` |

Blockers: 1 (fixed). Important: 3 (fixed). Confirmed 11 (5 local, 6 from the human's
checks by hand); refuted 4; findings in code changed by the clean-up: 0.

## Checked

- CI on `fa3a757`: 23 of 23 passed: unit (3.10, 3.13), integration (6), js, ui (2),
  container amd64 and arm64, smoke (8), `ci-ok`.
- The reviewer's local runs in round 7: `tests/test_docker.py` 69 passed; `openspec
  validate --specs --strict` 32 passed.
- The human's check by hand 2: 10 of 10 steps, the clone over ssh from the UI and
  `lado update` in a container (refused with the right text) among them; the Claude Code
  login by a token from `secrets/`.

## Not checked (residual risk)

- The reviewer did not run `make web` or the container tests; CI and the developer did.
- `releases/latest/download/compose.yaml` works only from the final 0.40.0 (D2).
- Not checked by hand: `.env` for Linux, the OpenCode and Kilo logins, `docker run`,
  update and way back on a real new version, a second LADO, the `↑` mark in the UI.

Found on the way: none.
