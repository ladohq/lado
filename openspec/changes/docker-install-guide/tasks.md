Tests first in each section; each task is one commit.

## 1. GitHub's host keys in the image

- [ ] 1.1 Unit tests (layer 1), `tests/test_docker.py`: `docker/ssh_known_hosts` has only
  `github.com` lines with the key types ed25519, ecdsa-sha2-nistp256 and rsa; the
  Dockerfile copies it to `/etc/ssh/ssh_known_hosts` (mode 644, root's); the build
  context's allowlist gains `!docker/ssh_known_hosts` and nothing else (D3, D4).
- [ ] 1.2 `docker/ssh_known_hosts` from `api.github.com/meta`, its fingerprints checked
  against docs.github.com; Dockerfile `COPY`; `Dockerfile.dockerignore`.
  `uv run pytest tests/test_docker.py -n auto`, `make lint`.
- [ ] 1.3 Container test (layer 7), `tests/container/test_access.py`: on a new home
  volume with no ssh agent, `ssh -T -o BatchMode=yes git@github.com` in lado's login
  shell fails with `Permission denied (publickey)`, not `Host key verification failed`,
  and `~/.ssh/known_hosts` is not made (D4). `make docker`, then `uv run pytest -m
  container -n0 -k host_key` (or CI's `container` job).

## 2. compose.yaml as a release asset

- [ ] 2.1 Unit test, `tests/test_release_workflow.py`: the `github-release` job's `gh
  release create` uploads `docker/compose.yaml#compose.yaml` beside `dist/*` (D2).
- [ ] 2.2 `.github/workflows/release.yml`; docs/release.md names the asset where it lists
  what a release publishes. `uv run pytest tests/test_release_workflow.py -n auto`.

## 3. The warning for a folder outside LADO_REPOS

- [ ] 3.1 Unit tests, `tests/test_runtime.py`: `runtime.outside_repos` gives the warning
  in a container for a folder outside, None for the folder itself, one below it, a link
  whose real path is below it, outside a container, and without `LADO_REPOS`;
  `start_session` (new and resume) carries it in `Started.warnings` (D5).
- [ ] 3.2 `runtime.OUTSIDE_REPOS`, `runtime.outside_repos`, the warning in
  `start_session`. `uv run pytest tests/test_runtime.py -n auto`.
- [ ] 3.3 Unit tests, the server's (`tests/test_server_launch.py` for the folder
  check, `tests/test_server_clones.py` for the clone target): `GET /api/folders` and `GET /api/clone-target`
  carry `warning` in a container, null outside (D5, D6).
- [ ] 3.4 `models.FolderInfo.warning`, `models.CloneTarget.warning`, `launch.folder_info`,
  `clones.py`; `make web-types`, both files committed.
- [ ] 3.5 vitest, `web/src/Launch.test.tsx`: the warning shows under Where after the check
  mark and under Clone into, Start stays enabled; none without the field (D6).
- [ ] 3.6 `web/src/Launch.tsx` as on mockup `task/lad-83/mockup-outside-repos.html`
  variant 2. `make web`.
- [ ] 3.7 UI e2e (layer 4), `tests/ui/`: a server with `LADO_CONTAINER=1` and
  `LADO_REPOS` shows the warning for a folder outside and none for one inside; a
  screenshot of each. `uv run pytest -m ui <file>`.
- [ ] 3.8 docs/design/ui.md, Launch and session control: the warning under Where and
  Clone into, the mockup's name.

## 4. The guide

- [ ] 4.1 Unit tests, `tests/test_docker.py`: `guide_steps` reads docs/install.md's
  `## Docker` code blocks. The first start, the update and the way back equal the
  header's. The download is `releases/latest/download/compose.yaml`. The `.env` block
  names every `${VAR}` of compose.yaml but `LADO_IMAGE` and `LADO_SECRETS`. The removal
  is `docker compose down` and `docker volume rm` of `<project>_home`. No `prune` in
  docs/, docker/ or README.md. README's Install links to `docs/install.md#docker`. The
  guide says `env | grep` and `unset`. Each header names the guide (D7, D8).
- [ ] 4.2 docs/install.md `## Docker` (contents list too), after Windows. It covers the
  prerequisites (Docker Desktop on a Mac, Docker Engine with the compose plugin on Linux),
  then these steps:
  - check the shell (`env | grep -E '^(LADO|COMPOSE)_'`, `unset`);
  - a folder of its own, download compose.yaml, `.env` with the values for a Mac and for
    Linux, `mkdir -m 700 secrets` and its files (`printf %s ... > secrets/GH_TOKEN`);
  - `docker compose up -d`, then `docker compose exec lado lado ui --no-open`;
  - log in: Claude Code inside first (`docker compose exec -it lado claude`), then a token
    from `claude setup-token`; OpenCode and Kilo; Codex not yet;
  - ssh (`ssh-add -l`; on a Mac `ssh-add --apple-use-keychain`);
  - the first session in a folder under the projects folder;
  - update, go back, a second LADO, the sessions, remove, `docker run`, and If something
    goes wrong (D1, D8, D9).
  Each part links to the header for the reference. README.md's Install gets a Docker
  block (three lines and the link). One line in each header points to the guide.
  `uv run pytest tests/test_docker.py -n auto`.
- [ ] 4.3 Check F13's fix (D9) against `docker/entrypoint.sh`. When a new container does
  not retry the owner change, write what does.

## 5. Records

- [ ] 5.1 AGENTS.md: Layout's `docker/` (the host keys file, the asset, the guide), the
  release paragraph if it lists the assets; CHANGELOG.md under the open version (D10).
- [ ] 5.2 The pull request carries the human's check by hand:
  - the branch, through `git worktree add`;
  - a clean folder, with its own `COMPOSE_PROJECT_NAME` and volume;
  - `env | grep LADO` and `unset`;
  - `make docker` and `LADO_IMAGE=lado:local`, or the file from the worktree in place of
    the asset;
  - the guide from scratch, to a session where an agent commits and pushes over ssh with
    no `accept-new`;
  - the warning for `/home/lado/app`;
  - removal by name.
  Only fake secrets appear in it.
- [ ] 5.3 `openspec validate docker-install-guide --strict`, `openspec validate --specs
  --strict`, `make lint`, `make test`.
