## Context

LAD-64 put LADO's image in `docker/`: Debian 12 (git 2.39, tmux 3.3a), the user `lado`
(uid 1000, `USER lado`), `/projects` made in the image and named by `LADO_REPOS` in the
`ENV` and in `docker/profile.sh` (`/etc/profile.d/lado.sh`, as the agents' environment
comes from `$SHELL -ilc`, `agent_env.resolve`, never from the container's environment),
tini as the entrypoint and `lado server --host 0.0.0.0 --port $LADO_PORT` as the command.
`docker/compose.yaml` mounts `LADO_PROJECTS` (required) at `/projects`. The container
tests (`tests/container/`) drive the `docker` CLI from the host; CI runs them on
`ubuntu-24.04` and `ubuntu-24.04-arm`, whose user is uid 1001.

Research LAD-52 (docs/research/docker-install.md): H6 shows a worker's worktree made in
the container `prunable` on the host and `git -C <worktree> status` failing there, as
`.git` files hold `/projects/...`; section 5.4 shows the owner problem of a Linux host and
that Docker Desktop shows a bind mount's root as `0:0` to any container user while it
maps the files to the host's user.

Facts checked for this design: git 2.39 honours `safe.directory` only in the system,
global and command-line config, and knows `*` but not a `<path>/*` prefix (that came with
git 2.46); `docker exec` with no `-u` runs as the image's `USER` by name, resolved in the
container's `/etc/passwd` at each exec, so a changed uid of `lado` holds for it;
`usermod -u` changes the owner only of files under the home that the old uid owned.

Root cause: the container sees the projects under another path (git's absolute links)
and another owner (Docker Engine maps no uids) than the host.

Options weighed for the path (the plan, research 5.3):
1. The same path inside as on the host (chosen): every stored path and git link is right
   on both sides; costs the host path in the compose file and once more in `docker run`.
2. A git 2.48+ with `worktree.useRelativePaths`: another base or a git built for the
   image, and LADO's worktree code checked with relative links; LADO's own stored
   `sessions.repo` would still be `/projects/...`, wrong on the host.
3. Only the UI's start folder in `/projects`: does not fix git.

Options for the owner (research 5.4): the user takes the projects' owner at start
(chosen; as VS Code Dev Containers do on Linux); rootless Podman or userns remapping (a
prepared user's setup, nothing LADO can do); projects in a volume (no host files in
Finder, M/L of UI work).

Options for how a root step runs while `docker exec` stays as `lado` (the human's choice,
2026-10-15: `docker exec` unchanged):
1. `USER lado` and a one-shot sudo rule for the entrypoint alone, removed by the step
   itself (chosen): `docker exec` as before; sudo is in the image but grants nothing once
   the container has started.
2. `USER root`, the entrypoint drops to `lado`: every `docker exec` needs `-u lado`, and a
   forgotten one quietly runs a second LADO as root with `/root/.lado`.
3. A setuid helper (fixuid): a third-party binary to pin and trust, for what sudo does.

Against ROADMAP.md and AGENTS.md: nothing under `providers/` changes and the image's
mechanism is provider-neutral (any CLI an agent runs inherits the uid and the profile);
one source of truth for the projects' path, `LADO_REPOS` (compose derives it from
`LADO_PROJECTS`); no silent drop: a folder LADO may not write in, or one not mounted, is
a warning in `docker logs` and in `lado doctor`; only what is used: no option for the uid,
it follows the folder.

## Decisions

- **D1. The path: `LADO_REPOS` is the one value.** compose: `volumes: -
  ${LADO_PROJECTS:?...}:${LADO_PROJECTS:?...}` and `environment: LADO_REPOS:
  ${LADO_PROJECTS:?...}` (the same message as today). `docker run`: `-v "$P:$P" -e
  LADO_REPOS="$P"`. The image's `ENV LADO_REPOS=/projects` stays the default and
  `/projects` stays in the image. No detection of mounts (`/proc/self/mountinfo`): the
  container cannot know the host's path, and a guess would be a hidden fallback.
- **D2. One entrypoint script, `docker/entrypoint.sh`**, copied to
  `/usr/local/bin/lado-entrypoint`; `ENTRYPOINT ["/usr/bin/tini", "--",
  "/usr/local/bin/lado-entrypoint"]`, `CMD` unchanged (the script ends with `exec "$@"`).
  POSIX `sh`, no bashisms. Phases, chosen by who runs it:
  1. As `lado` while the marker `/etc/lado/first-start` exists: `exec sudo -E -n
     /usr/local/bin/lado-entrypoint "$@"`.
  2. As root: remove `/etc/sudoers.d/lado-entrypoint` and the marker first, then D3 and
     D4, then `exec setpriv --reuid=lado --regid=lado --init-groups --
     /usr/local/bin/lado-entrypoint "$@"` with `HOME=/home/lado USER=lado LOGNAME=lado`.
  3. As `lado` with no marker (after phase 2, or on a restart, where `USER lado` resolves
     to the uid taken before): D5's checks, then `exec "$@"`.
  Phase 1 is only for the user named `lado` (`id -un`): a container started with
  `--user <uid>` goes to phase 3 as that uid. A failing step of phase 2 stops the container with its message (`set -eu`): the rule
  and the marker are gone already, so the next start is phase 3 with uid 1000, and the
  human sees why in `docker logs`.
- **D3. The uid and gid.** `stat -c '%u %g' "$LADO_REPOS"`; when it is no folder, or the
  uid is 0, or uid and gid are `lado`'s already, nothing changes. Else `groupmod -o -g
  <gid> lado` and `usermod -o -u <uid> -g <gid> lado` (`-o`: a host's gid such as 100
  may exist in the image). Then, whatever the uid, when anything under `/home/lado` has
  another owner than `lado`'s uid and gid (`find /home/lado ! -user lado -o ! -group lado
  -print -quit`), `chown -R lado:lado /home/lado`: a home volume of an earlier container
  with another uid follows. `/opt` is left as it is (Out of scope).
- **D4. LADO_REPOS for the agents.** Phase 2 writes `/etc/profile.d/lado-repos.sh`,
  `export LADO_REPOS='<value>'` with the value single-quoted (a `'` in it written as
  `'\''`), mode 644, also for the default `/projects`. `docker/profile.sh` drops its
  `LADO_REPOS` line; `tests/test_docker.py`'s comparison of profile.sh and `ENV` leaves
  `LADO_REPOS` out and a new test checks the entrypoint writes it.
- **D5. Warnings at start**, phase 3, on stderr (`docker logs`), one line each, the server
  started anyway: `lado: warning: LADO_REPOS is not a folder in the container: <path>;
  mount the host's folder at this same path`, or, for a folder where a probe file cannot
  be made (`mktemp "$LADO_REPOS/.lado-write-check.XXXXXX"`, removed at once), `lado:
  warning: LADO may not write in LADO_REPOS <path>`. A `LADO_REPOS` that is not absolute
  gets neither (LADO ignores it; `lado doctor` says so).
- **D6. The sudo rule.** Package `sudo` from Debian; `/etc/sudoers.d/lado-entrypoint`,
  mode 0440, the one line `lado ALL=(root) NOPASSWD:SETENV: /usr/local/bin/lado-entrypoint`
  (SETENV for `-E`: the server needs the container's `LADO_PORT`, `LADO_REPOS` and the
  rest), checked at build with `visudo -cf`. The marker `/etc/lado/first-start` (root's,
  readable) is made in the image. Phase 2 deletes both before it does anything else.
- **D7. git's trust.** `git config --system --add safe.directory '*'` in the Dockerfile:
  the container has one user, and after D3 the files are its own on Linux; on Docker
  Desktop the owner it sees may flicker (H6's benchmark), which `*` covers.
- **D8. The doctor's write check.** `doctor.check_repos_folder`, after the folder check:
  `tempfile.mkstemp(prefix=".lado-doctor-", dir=folder)`, closed and removed at once; an
  `OSError` is `warn` `LADO may not write in LADO_REPOS <path>: <strerror>` with the hint
  `give your user write access to it; in LADO's image on Linux, the folder's owner gives
  the container's user its uid`. Not `os.access`: on a Docker Desktop bind mount the root
  shows `0:0` and `os.access` would say no while writes succeed.
- **D9. Container tests**, `tests/container/test_projects.py` (marker `container`):
  - helpers: `run_container` takes the home volume's name (default `<name>-home`, as
    now) so a test can recreate with the same volume; a `projects_volume(owner)` fixture
    makes a named volume (`<PREFIX>…-proj`, removed after) owned by `<uid>:<gid>` through
    `docker run --rm -u 0 --entrypoint chown`; the session's teardown check counts it
    (its name has the prefix).
  - the host path: the test's `tmp_path/projects` mounted at the same path with
    `LADO_REPOS`; a repository made on the host (`git init`, a commit); the Claude Code
    session of `test_image.py` (fake endpoint, its setup moved into a helper both use)
    started on it; a worker spawned (`runtime.spawn_worker` through LADO's Python in the
    container); as `lado` (`docker exec`) a file written and committed in its worktree;
    then on the host `git -C <worktree> status`, `git worktree list --porcelain` without
    `prunable`, the branch's commit, `os.stat` of the file and of the commit's object
    `== os.getuid()`; the worker's process has `LADO_REPOS=<host path>`; `lado stop
    --all`.
  - the owner: a projects volume owned by 2001 → `id -u` 2001, the server healthy, no
    `sudo -n true`, a `docker restart` keeps 2001; the container removed (the home volume
    kept), a new one with that home and a projects volume owned by 2002 → `id -u` 2002,
    `find /home/lado ! -uid 2002` empty, `lado doctor` no `[FAIL]`, `lado ls` exit 0.
  - owner 0 (a volume chowned `0:0`, mode 755) → uid 1000 and the warning line in
    `docker logs`; `-e LADO_REPOS=/nowhere` → the not-mounted line.
  - compose: `test_compose_serves_on_lado_port` also checks `lado doctor`'s
    `Repositories folder: <tmp_path> (LADO_REPOS)`.
  The host-path test's ownership assertion holds on the Linux runner (uid 1001, D3) and
  on Docker Desktop (it maps to the host's user), so it never skips.
- **D10. Unit tests**, `tests/test_docker.py`: compose's projects volume is
  `${LADO_PROJECTS:?…}:${LADO_PROJECTS:?…}` and `LADO_REPOS` is `${LADO_PROJECTS:?…}`;
  profile.sh has no `LADO_REPOS`; the entrypoint line, the sudoers line and its mode, the
  marker, `safe.directory '*'`; the dockerignore allowlist adds `!docker/entrypoint.sh`.
  The doctor's write check in the doctor's unit tests (a read-only folder: `chmod 555`,
  skipped as root; the folder holds no leftover file).
- **D11. Docs.** The Dockerfile's and compose's header comments show the same-path form;
  AGENTS.md's `docker/` paragraph (entrypoint, uid, `safe.directory`, `LADO_REPOS` from
  the container) and its container tests list; CHANGELOG.md 0.39.0: the image line says
  the projects are at the host's path and the user takes their owner, and a line for the
  doctor's warning.
