The plan with each task's tests: `docs/superpowers/plans/2026-11-19-container-without-ssh-agent.md`.

## 1. The image and compose

- [ ] 1.1 compose binds no ssh socket; the image drops the socket's program, sudo rule,
  profile file, `/run/lado` and GitHub's host keys; the entrypoint's ssh block goes; the
  allowlist and headers follow (D1, D2). Check: `tests/test_docker.py`.

## 2. The installer

- [ ] 2.1 No `find_ssh_agent`, no `LADO_SSH_AGENT` written; a rerun keeps the line and
  prints the note (D3). Check: `tests/test_install_sh.py`, `tests/test_install_ps1.py`.

## 3. The clone's ssh hint in the container

- [ ] 3.1 `clone._told`'s container texts and way for the ssh kinds (D4). Check:
  `tests/test_clone.py`, `tests/test_gitcache.py`.

## 4. The add form

- [ ] 4.1 Address starts empty with the placeholder `github.com or gitlab.example.com`;
  `GITLAB_COM` goes (D5). Check: `tests/ui/test_git_servers_section.py`, `make web`;
  screenshot.

## 5. End-to-end tests

- [ ] 5.1 The clone's `Add git server ↗` in a container's UI. Check: `tests/ui/test_launch.py`;
  screenshot.
- [ ] 5.2 The container with an old `LADO_SSH_AGENT` line: no socket, no `SSH_AUTH_SOCK`,
  no ssh line; `sudo -n -l` grants nothing; the ssh agent's tests removed (D7). Check:
  `make test-container` (or CI).

## 6. Docs and CHANGELOG

- [ ] 6.1 docs/install.md (`.env` examples, the token's extra scopes, git over ssh, the
  pitfall, the way back), docs/design/modules.md, docs/testing.md, docs/cli.md,
  docs/design/ui.md, CHANGELOG 0.48.0. Check: `tests/test_docker.py`'s guide tests,
  `grep -rn "LADO_SSH_AGENT" docs docker` finds only the way back and CHANGELOG's history.

## 7. Regression run

- [ ] 7.1 `make lint`, `make test`, the changed integration and UI files with their markers,
  `make web`, `openspec validate container-without-ssh-agent --strict`, the trial archive.
