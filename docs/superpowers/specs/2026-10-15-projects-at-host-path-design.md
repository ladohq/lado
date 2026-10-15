# The projects at the host's path and owner in LADO's image: design

Task: LAD-69. Change: `openspec/changes/projects-at-host-path/` (proposal, deltas
`container` and `repos-folder`, `design.md` D1-D11). Step T4 of the Docker install plan
(docs/research/docker-install-plan.md; T4 and T5 of the first plan); research
docs/research/docker-install.md, sections 5.3 and 5.4, hands-on check H6.

## Problem

The image (LAD-64) mounts the human's projects at `/projects`. git 2.39 writes absolute
paths into a worktree's `.git` file and the repository's `worktrees/` record, so a worker's
worktree made in the container points at `/projects/...`, which the host does not have:
`git worktree list` on the host says `prunable`, `git -C <worktree> status` fails, an IDE
cannot open it, and a `git worktree prune` or `git gc` on the host drops git's record, after
which the worker's finish in the container fails with `is not a working tree`.

On a Linux host Docker Engine maps no uids: the container's `lado` is uid 1000, the host's
user usually another (GitHub's runner 1001). Agents then cannot write in the projects, or
leave files the host's user does not own, and git refuses the repositories as of "dubious
ownership".

Root cause: the container sees the projects under another path and another owner than the
host, and both git and the file system record them.

## Goal

A user mounts their projects folder once and works on it from the container and from the
host alike: a worker's worktree is a working tree on the host, the files the agents write
are the host user's own, and nothing changes in how they reach LADO (`docker exec lado lado
ui --no-open`, the compose file).

## What the user sees

compose, as before:

```
$ export LADO_PROJECTS=~/projects
$ docker compose up -d
$ docker compose exec lado lado doctor | grep Repositories
[ok  ] Repositories folder: /Users/me/projects (LADO_REPOS)
```

`docker run`, the path written twice:

```
$ docker run -d --name lado -p 127.0.0.1:8765:8765 -v lado-home:/home/lado \
    -v "$HOME/projects:$HOME/projects" -e LADO_REPOS="$HOME/projects" lado:local
$ docker exec lado lado ui --no-open
http://127.0.0.1:8765/?token=...
```

After a worker committed in the container, on the host:

```
$ git -C ~/projects/app worktree list
/home/me/projects/app                                cc24eb5 [main]
/home/me/projects/app/.lado/worktrees/demo/worker    718c0e9 [lado/demo/worker]
$ ls -ln ~/projects/app/.lado/worktrees/demo/worker
-rw-r--r-- 1 1001 1001 24 ... hello.txt
```

A folder not mounted at the given path, or one the container's user may not write in:

```
$ docker logs lado
lado: warning: LADO_REPOS is not a folder in the container: /home/me/projects; mount the host's folder at this same path
```

and `lado doctor` anywhere: `[warn] Repositories folder: LADO may not write in LADO_REPOS
<path>: Permission denied`.

## Approach

- **Same path** (D1): compose mounts `LADO_PROJECTS` at itself and sets `LADO_REPOS`; the
  `docker run` form adds `-e LADO_REPOS`. `/projects` stays the image's default.
- **The owner** (D2, D3, D6): the image stays `USER lado`. Its entrypoint, at a container's
  first start, runs itself again as root through a sudo rule that names only it; that root
  phase deletes the rule and its marker first, gives `lado` the uid and gid of
  `LADO_REPOS`'s owner unless that is 0 or already `lado`'s, moves the home volume to them,
  writes `LADO_REPOS` for the agents' login shells (D4), and drops to `lado` with
  `setpriv` to start the server. `docker exec` resolves `lado` by name, so it gets the new
  uid; a restart starts as it directly.
- **git** (D7): `safe.directory = *` in the image's system config.
- **Warnings** (D5, D8): the entrypoint's lines in `docker logs`; `lado doctor`'s write
  probe everywhere.

## Requirements and their test layers

| Requirement (delta) | Layer | Test |
|---|---|---|
| container: one docker run (uid note) | 7 container | existing `test_image.py` stays green |
| container: agents get the container's `LADO_REPOS` | 1 unit, 7 container | `test_docker.py` (profile.sh without it); `test_projects.py` (the worker's environ) |
| container: compose at the host's path | 1 unit, 7 container | `test_docker.py` (the volume and env lines); `test_compose_serves_on_lado_port` (doctor's line) |
| container: a worktree made inside works on the host | 7 container | `test_a_workers_worktree_works_on_the_host` |
| container: the user takes the owner | 7 container | `test_the_user_takes_the_projects_owner`, `test_recreated_with_another_owner_keeps_the_home`, `test_owner_0_keeps_1000_and_warns`, `test_lado_repos_not_mounted_warns` |
| container: git trusts every repository | 1 unit, 7 container | `test_docker.py` (the config line); the owner tests run git on files of another uid |
| repos-folder: doctor's write check | 1 unit | doctor's tests (a read-only folder, no leftover) |

The entrypoint is a shell script whose effects need a real container (usermod, sudo,
volumes): its lowest layer is 7. No integration test: nothing of LADO's processes changes.
Regression: `make lint`, `make test`, `make docker && make test-container`,
`openspec validate --specs --strict`, and CI's `container (amd64)` and `container (arm64)`.

## Acceptance criteria

- AC-1 With compose, the container sees `LADO_PROJECTS` at the same path and `LADO_REPOS`
  is that path (the doctor's line); `docker run` with `-v P:P -e LADO_REPOS=P` the same.
- AC-2 A worker in the container commits in a host folder; on the host `git -C <worktree>
  status` succeeds and `git worktree list` has no `prunable`.
- AC-3 On CI's Linux runner (uid 1001) the files and commit objects an agent's work made
  belong to uid 1001 on the host; on a Mac to the host's user.
- AC-4 A container whose projects belong to another uid runs as that uid; recreated with a
  third uid and the same home volume, it runs, its home is that uid's, `lado doctor` has
  no `[FAIL]`; a restart keeps the uid.
- AC-5 An owner of 0 keeps uid 1000; a folder not writable or not mounted is one warning
  line in `docker logs`; the server starts in both.
- AC-6 `docker exec <container> lado ui --no-open` works unchanged and runs as `lado`'s
  uid; no `sudo` works as `lado` after the start.
- AC-7 `lado doctor` warns `LADO may not write in LADO_REPOS <path>` for a folder where it
  cannot make a file, and leaves no file behind.
- AC-8 CI's `container (amd64)` and `container (arm64)` are green with the new tests.
- AC-9 By hand on a Mac: `make docker`, a container with the projects at their path, a
  session in the UI on a project there, a worker commits; on the host `git worktree list`
  is clean.

## Version

No CLI option, MCP tool or schema change. The image is unreleased; its change and the
doctor's warning go into 0.39.0's notes (unreleased), no further bump.
