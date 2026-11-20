# The container without the host's ssh agent: Implementation Plan

**Goal:** LADO's container has no ssh: compose binds no ssh agent, the image drops the
socket's program, rule, profile file and GitHub's host keys; the installer writes no
`LADO_SSH_AGENT` and notes an old one as unused; the clone's ssh hint in the container
points at Settings → Git servers; the add form fills in no server; the guides and
CHANGELOG say so.

**Architecture:** removals in `docker/` (D1, D2); `install.sh`'s rerun note (D3);
`clone._told`'s container branch for the ssh kinds (D4); `GitServers.tsx`'s initial value
and placeholder (D5); docs with the way back (D6). Tests per layer (D7).

**Tech Stack:** POSIX sh, Docker/compose, Python 3.10+ (standard library), React +
TypeScript, pytest (`-n auto`, `-m ui`, `-m container`), Playwright's Chromium.

**Spec:** `openspec/changes/container-without-ssh-agent/` (proposal, deltas, `design.md`
D1–D7) and `docs/superpowers/specs/2026-11-19-container-without-ssh-agent-design.md`
(texts, tests per requirement, docs, manual check). Mockup: the run's
`mockup-git-servers.html` (placeholder 1).

## Global Constraints

- The texts are those of the deltas and the design doc, word for word; another wording needs
  a reason in the build report.
- Nothing outside Docker changes: `agent_env.SHELL_BASE` keeps `SSH_AUTH_SOCK`; clone hints
  outside the container stay.
- No line about `LADO_SSH_AGENT` in the container, its logs or `lado doctor` (#7456).
- `.env`'s `LADO_SSH_AGENT` line is never removed by the installer.
- Nothing in code, docs, specs or the UI names the epic's stages or `docs/epics/`.
- CHANGELOG: extend 0.48.0 (unreleased); no new version.
- The pull request carries the design doc's manual check from the start, each command
  checked against the code of the version it runs.

## Review Focus

- No leftover of the ssh agent in `docker/`, the docs or the tests (`grep -rn
  "SSH_AGENT\|ssh-agent\|ssh_known_hosts\|SSH_AUTH_SOCK" docker docs/install.md
  docs/design docs/testing.md tests/test_docker.py tests/container`).
- The clone's container branch reads saved servers without making lado.db.

## Task 1: The image and compose without the ssh agent (D1, D2)

Files: `docker/compose.yaml`, `docker/Dockerfile`, `docker/Dockerfile.dockerignore`,
`docker/entrypoint.sh`, `docker/profile.sh`; delete `docker/ssh-agent-socket.sh`,
`docker/ssh-agent-env.sh`, `docker/ssh_known_hosts`.

- [ ] Tests first, `tests/test_docker.py`: drop the tests of the socket program, the rule,
  `ssh-agent-env.sh`, the host keys and the bind; add: compose has no volume whose target
  or source names ssh and no `LADO_SSH_AGENT`; the Dockerfile has no `ssh-agent`,
  `ssh_known_hosts`, `/run/lado` or second `sudoers.d` file; the allowlist is the wheel,
  `profile.sh`, `entrypoint.sh`, `mise.toml`; no file of `docker/` names `SSH_AUTH_SOCK`;
  the headers name `no ssh` and not `LADO_SSH_AGENT`. Fail, then change, then pass:
  `uv run pytest tests/test_docker.py -n auto`.
- [ ] The entrypoint loses its ssh block and the `source`; the Dockerfile's comment on
  `openssh-client` says why it stays (D1).
- [ ] Commit: `LADO's container binds no ssh agent and carries no ssh host keys (LAD-300)`.

## Task 2: The installer (D3)

Files: `docker/install.sh`, `tests/test_install_sh.py`.

- [ ] Tests: macOS fresh install has no `LADO_SSH_AGENT` and no `ssh agent` in its output;
  Linux with `SSH_AUTH_SOCK` a socket has none; an update from 0.47.0 with the line keeps
  it and prints the note once; a rerun of the same version prints it; no line, no note.
- [ ] Drop `find_ssh_agent` and its `.env` line; in `rerun`, the note when `env_value
  LADO_SSH_AGENT` is not empty.
- [ ] `uv run pytest tests/test_install_sh.py tests/test_install_ps1.py -n auto`. Commit.

## Task 3: The clone's ssh hint in the container (D4)

Files: `src/lado/clone.py`, `tests/test_clone.py`.

- [ ] Tests with `update.in_container` patched true: `git@github.com:a/b.git` and
  `ssh://git@github.com:22/a/b` for both kinds, github.com not saved: the reason, the hint
  and `ServerWay("add", "github.com", "https://github.com", <page>)`; port 2222,
  `alice@github.com:a/b`, and a saved `https://github.com` reached over ssh: the https
  reason, no hint, no way; `clone.explain` gives the same text; with no lado.db none is
  made; patched false: today's texts.
- [ ] `_told`: for `ssh_denied`/`host_key`, `address.scheme == "ssh"` and
  `update.in_container()`, the container texts; `git_servers.address(f"https://{host}")`
  for the way.
- [ ] `uv run pytest tests/test_clone.py tests/test_gitcache.py -n auto`. Commit.

## Task 4: The add form starts empty (D5)

Files: `web/src/GitServers.tsx`, `tests/ui/test_git_servers_section.py`, `docs/design/ui.md`.

- [ ] UI e2e first: empty list → Address empty, focused, placeholder `github.com or
  gitlab.example.com`, no `answers.` line; gitlab.com saved → empty; `?add=https://x.example`
  fills it; typing `gitlab.com` gives `GitLab answers.` and its scopes; github.com gives
  `scope repo` (kept).
- [ ] `initial={addAt ?? ""}`, drop `GITLAB_COM`, the placeholder. `make web`;
  `uv run pytest -m ui <the file>`. Screenshot of the empty form for `build-report`.
- [ ] Commit.

## Task 5: The clone's hint in the UI, end to end (D4, D7)

Files: `tests/ui/test_launch.py`.

- [ ] A server started with `LADO_CONTAINER=1`, a repository URL `git@github.com:a/b.git`
  whose listing fails with `Permission denied (publickey)` (the test's fake git or ssh, as
  the file does for other failures): the reason under Repository URL and `Add git server ↗`
  linking Settings → Git servers with `add=https://github.com`. Screenshot. Commit.

## Task 6: The container test (D7)

Files: `tests/container/test_access.py`, `tests/container/test_image.py`, `docs/testing.md`.

- [ ] Drop the ssh agent's tests and fixture (`ssh_agent`, the host keys' test, the rule's
  test); add `test_an_old_ssh_agent_line_changes_nothing` (the design doc's table) and the
  `sudo -n -l` check; drop the socket from `test_image.py`'s bind filter.
- [ ] `make docker && make test-container` when Docker is at hand, else "written, run in CI"
  in the build report. Commit.

## Task 7: Docs and CHANGELOG

Files: `docs/install.md`, `docker/compose.yaml` and `docker/Dockerfile` headers (Task 1),
`docs/design/modules.md`, `docs/testing.md`, `docs/cli.md`, `docs/design/ui.md`,
`CHANGELOG.md`.

- [ ] As the design doc's Docs says; `tests/test_docker.py`'s guide checks pass.
- [ ] Commit: `The guides say LADO's container has no ssh (LAD-300)`.

## Regression run

`make lint`; `make test`; `uv run pytest -m integration -n auto tests/integration/test_git_server_access.py`
(the ssh rewrite, unchanged); `uv run pytest -m ui` on the changed files; `make web`;
`openspec validate container-without-ssh-agent --strict`; the trial archive of the settings'
Checks. CI runs the container tests on amd64 and arm64.
