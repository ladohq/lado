# LAD-69 projects-at-host-path: review report

Pull request #56 `feature/lad-69-projects-at-host-path` → `main`. Scale: full, reviewed
for breadth first, at most two external rounds. Head reviewed last: `3560059` (= the
remote head); the archive commit follows it. `providers/`, `hooks.py`, `mcp_server.py`,
`runtime.py`, `agent_env.py` and `tests/live/` did not change, so live tests are not
needed before the merge.

## Rounds

- **Round 1, local** (breadth over `origin/main...30eb16f`): F1-F3.
- **Round 2, local** (precision over `30eb16f..4edd40e`): F8.
- **Round 1, external** (Claude Code GitHub Action, the whole pull request
  `origin/main...4edd40e`; request 23:36:40Z, "Claude finished" 23:38:05Z): F4-F9.
- **Round 3, local** (precision over `4edd40e..2416899`): F10, F11.
- **Round 4, local** (precision over `2416899..3560059`): F16 (minor), nothing to fix.
- **Round 2, external** (the last by the cap; delta `4edd40e..3560059`; request
  00:06:06Z, "Claude finished" 00:07:05Z, verdict "good to merge"): F12-F15, all minor or
  refuted. The answer is posted on the pull request.
- **Round 5, local** (precision; a return after the human rejected the merge gate asking
  for exact steps to check it by hand on a Mac): no code changed, the head stayed
  `3560059`; the pull request's description gained "How to check it by hand on a Mac" (10
  steps). The reviewer ran steps 2-6, 9b (compose without `LADO_PROJECTS`) and 10 itself
  on Docker Desktop (arm64) with the image of `3560059`: health answers with no warning,
  `lado doctor` shows the host's path as `ok`, `lado` runs as uid 1000 with no sudo left,
  a worktree made in the container is not `prunable` on the host and its file is the
  host user's, a restart serves again, compose refuses without `LADO_PROJECTS`. No new
  finding.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"good to merge" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (security) | the sudo rule with SETENV and a `setpriv` from the caller's PATH gave root where the rule stayed (entrypoint replaced) | confirmed | important | fixed in `4edd40e`, with tests |
| F2 | 1 | local | a projects folder `<uid>:0` made root's group `lado`'s primary group | confirmed | minor | fixed in `4edd40e`, with a test |
| F3 | 1 | local (tests) | `safe.directory '*'` has only a static test of the Dockerfile's line | confirmed | minor | declined: the unit test holds the line; the external reviewer agreed |
| F4 | ext. 1 | external | the container did not start with no-new-privileges or `--cap-drop ALL` (a regression against main) | confirmed | important | fixed in `2416899` (`may_become_root`), with a test |
| F5 | ext. 1 | external | a rule left behind may give a privileged gid | refuted | — | dropped: the rule is one-shot; no folder of the image has such an owner |
| F6 | ext. 1 | external | a relative `LADO_PROJECTS` in compose | confirmed | minor | fixed in `2416899` (compose header) |
| F7 | ext. 1 | external | `--user root` now runs the command as `lado` | confirmed | minor | documented in `2416899` (Dockerfile header, D2) |
| F8 | 2 / ext. 1 | local + external | a long Dockerfile comment line mixing two subjects | confirmed | minor | fixed in `2416899` |
| F9 | ext. 1 | external | no doctor test that the probe file is gone | refuted | — | dropped: `test_doctor.py::test_the_write_check_leaves_no_file` |
| F10 | 3 | local (class of F4) | a read-only root file system stopped the start at the rule's `rm -f` (a regression against main) | confirmed | important | fixed in `3560059` (`read_only_root` by mountinfo; `rm` only warns), with a test |
| F11 | 3 | local | an entrypoint comment line of 131 characters | confirmed | minor | fixed in `3560059` |
| F12 | ext. 2 | external | `docker run --user root --cap-drop ALL` stops at `setpriv` (no SETUID); on main it ran as root | confirmed | minor | declined: a rare combination, a loud failure, `--user root`'s new behaviour documented; the human's call at the merge |
| F13 | ext. 2 | external | a partial owner change (`groupmod` ok, `usermod -u` not) is not retried: the marker is gone | confirmed | minor | declined: the warning prints the resulting `uid:gid` |
| F14 | ext. 2 | external | without root the marker stays and the warning repeats at each start | refuted | — | dropped: on purpose (D2) |
| F15 | ext. 2 | external | the `kept` text holds only while the image's default `lado-repos.sh` stays | refuted | — | dropped: without root only the image's build writes it |
| F16 | 4 | local | a new spec line longer than the others | confirmed | minor | declined: openspec valid, the meaning unchanged |

Three important findings (F1, F4, F10), each fixed with a test seen red first. F4 and F10
are one class: a start that fails under a hardened container setting, introduced by
review fixes.

## Checks

- CI of PR #56 on `3560059`: 23 of 23 green, `container (amd64)`, `container (arm64)` and
  `ci-ok` included (the Linux runner's uid 1001 checks the owner part).
- The developer's runs: `make test` 3182 passed, `make test-container` 17 passed on the
  Mac. The reviewer's round 1: lint, `test_doctor.py` / `test_docker.py` 102 passed,
  openspec 26 passed.

## Not checked (residual risk)

- Failures of `rm`, `usermod` / `groupmod` and `chown` in the root step cannot be caused
  in a container with root; their warning branches are checked by reading only.
- Restrictions the checks before sudo do not see: seccomp, AppArmor / SELinux, user
  namespaces (rootless Docker, Podman). sudo may fail there after the `exec`, and the
  container does not start.
- With the entrypoint replaced, the rule left behind lets `lado` take once the uid of any
  folder's owner (in the image only `_apt`, unprivileged).
- Step 7 of the manual steps (a real agent with a Claude login commits in a worktree in
  the container) was run by no one; `tests/container/test_projects.py` covers the same
  path with the fake endpoint.
- The reviewer ran `docker volume prune -f` on the review machine in round 2, which
  removes every unused anonymous Docker volume; what went is unknown. The repository was
  not touched; since then only its own containers and volumes by name.

## Found on the way

None.
