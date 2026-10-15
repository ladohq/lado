Task: LAD-69

## Why

LADO's image (LAD-64) mounts the human's projects at `/projects`, while on the host they
live elsewhere (`~/projects`). git 2.39, the image's, links a worktree to its repository
with absolute paths, so a worker's worktree made in the container is `prunable` on the
host and `git -C <worktree> status` there fails (research LAD-52, H6 and section 5.3); an
IDE on the host cannot open it, and a `git worktree prune` or `git gc` on the host later
breaks the worker's finish in the container. On a Linux host (Docker Engine) the
container's user is uid 1000 and the host's folder belongs to another uid (GitHub's runner:
1001), so the agents either cannot write in the projects or leave files the host's user
does not own (section 5.4). This is step T4 of the Docker install plan
(docs/research/docker-install-plan.md, T4 and T5 of the first plan in one).

Root cause: the container sees the projects under another path and another owner than the
host, and git and the file system record both.

## What Changes

- **The projects at the host's path.** `docker/compose.yaml` mounts `LADO_PROJECTS` at
  that same path (`${LADO_PROJECTS}:${LADO_PROJECTS}`) and sets `LADO_REPOS` to it. With
  `docker run` the human writes the path twice, `-v "$HOME/projects:$HOME/projects" -e
  LADO_REPOS="$HOME/projects"`, and no other file. Without `-e LADO_REPOS` the image keeps
  `/projects`, so a container without a projects mount still starts.
- **LADO_REPOS reaches the agents.** The agents' environment comes from the login shell,
  not from the container's environment, so the container's start writes the container's
  `LADO_REPOS` into a profile script of its own (`/etc/profile.d/lado-repos.sh`);
  `docker/profile.sh` no longer sets it.
- **git trusts the projects.** The image's system git config has `safe.directory = *`
  (git 2.39 has no `<path>/*` form), so git never refuses a repository there as of
  "dubious ownership".
- **The user `lado` takes the projects' owner.** At the container's first start a one-shot
  root step gives `lado` the uid and gid of `LADO_REPOS`'s owner (Docker Engine on Linux);
  an owner of 0 (how Docker Desktop shows a bind mount) changes nothing; the home volume
  follows the uid (`chown -R` when its owner differs, so a container recreated with
  another uid keeps working with the same volume). The image's user stays `lado`, so
  `docker exec lado lado ui --no-open` is as before and runs under the new uid. The root
  step is reached through a sudo rule for the entrypoint alone, which the step removes
  first; no agent can become root.
- **A projects folder LADO may not write in is named.** The container's start prints a
  warning in `docker logs` when `LADO_REPOS` is no folder (not mounted at that path) or the
  user `lado` may not write in it, and `lado doctor`'s `Repositories folder` check warns
  `LADO may not write in LADO_REPOS <path>` everywhere, in and out of a container.
- **Container tests** (layer 7, CI's `container (amd64)` and `container (arm64)`): a
  worker in the container commits in a host folder mounted at the same path, and on the
  host `git -C <worktree> status` works, `git worktree list` has no `prunable`, the files
  the container wrote belong to the host's user (uid 1001 on CI's runner), and the agent's
  `LADO_REPOS` is the host's path; a container with projects owned by another uid runs as
  that uid, and recreated with another uid keeps working with the same home volume; an
  owner of 0 leaves uid 1000 and warns; a restart keeps the uid; no `sudo` is left.

## Scope

Changed: `docker/Dockerfile` (sudo, the sudoers rule, the entrypoint, `safe.directory`),
`docker/profile.sh` (no `LADO_REPOS`), `docker/compose.yaml`, `docker/Dockerfile.dockerignore`
(the entrypoint), new `docker/entrypoint.sh`; `src/lado/doctor.py`
(`check_repos_folder`'s write check); tests: `tests/test_docker.py`, `tests/test_doctor.py`
(or the file that tests `check_repos_folder`), `tests/container/` (helpers for a given home
volume and projects, new tests); AGENTS.md (Layout: `docker/`; Commands: container tests),
CHANGELOG.md. Capabilities: `container` and `repos-folder` change. No schema change, no
MCP tool, no CLI option. Version: the image is unreleased (0.39.0 is not out yet); the
doctor's new warning and the image's changes go into 0.39.0's notes, no further bump.

## Out of scope

- Global installs by agents into `/opt` (`npm i -g`, `uv tool install`) after the uid
  changed: `/opt` stays uid 1000's, as a recursive `chown` of the programs' layer
  (Claude Code alone is ~200 MB) at each new container would copy it and take minutes;
  toolchains come with T9 (mise). The human's decision, 2026-10-15.
- Windows and WSL host paths: the plan's later steps (research section 6).
- Relative worktree links (`worktree.useRelativePaths`, git 2.48+): Debian 12 has 2.39;
  the same path makes them unnecessary.
- Detecting the old form `-v ~/projects:/projects` and warning about it: the container
  cannot know the host's path; the documentation stops naming that form. The human's
  decision.
- An entrypoint started as root with `docker exec -u lado`: each `docker exec` would need
  `-u lado`, and a forgotten one would quietly run a second LADO as root with its own
  LADO_HOME. The human's decision.
- Stopping and resuming the container's sessions (T6), publishing the image (T7), the ssh
  agent and tokens (T10).
- `docs/research/docker-install-plan.md`: updated by another session's supervisor.

## Impact

- Users of the image: the compose file needs nothing new (`LADO_PROJECTS` as before, now
  seen at its own path); `docker run` adds `-e LADO_REPOS=<path>` and mounts at that path.
  Sessions started on `/projects` before keep their stored path; a new session takes the
  new one.
- `lado doctor` everywhere: a new `warn` for a repositories folder LADO may not write in.
- Spec: `container` (one docker run, the agents' environment, compose; new: the host's
  path, the owner's uid, git's trust); `repos-folder` (the doctor's check).
