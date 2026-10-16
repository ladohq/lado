# Secrets and git access in LADO's container (LAD-76)

Change: `openspec/changes/container-secrets-and-git/` (proposal, delta specs of
`agent-variables` and `container`, `design.md` with the decisions D1-D14). This document
is the human's view: what a user of the image gets, what is accepted, and how the human
checks it.

## What a user gets

Today an agent in LADO's container cannot commit (no git name or email), cannot push to
GitHub over https, reaches the host's ssh agent only through root's group, and a kit whose
MCP server needs a key (kit tracker-yougile's `YOUGILE_API_KEY`) is refused, since nothing
puts a variable into the agents' environment.

After this change, next to `compose.yaml`:

```
.env                       LADO_VERSION, LADO_PROJECTS, and now:
                           LADO_GIT_NAME="Ann Lee"
                           LADO_GIT_EMAIL=ann@example.com
                           LADO_SSH_AGENT=/run/host-services/ssh-auth.sock   # Mac; Linux: your $SSH_AUTH_SOCK
secrets/                   mkdir -m 700 secrets; one file per variable:
  GH_TOKEN                   git push over https and gh api
  YOUGILE_API_KEY            a kit's key
  CLAUDE_CODE_OAUTH_TOKEN    Claude Code's login (from `claude setup-token`)
```

- **Variables from files.**
  - Every agent gets each file of `secrets/` as a variable; the file name is the
    variable's name.
  - A new or changed file reaches the agents started after it, with no restart.
  - `docker inspect` shows only the folder's path, never a value.
  - `lado doctor` lists the names it takes and warns about files it does not take: a bad
    name, `PATH` or `LADO_…`, too large, or not text. `lado start` and the UI's start
    name them too.
- **git name and email** come from `.env` at every start of the container; without them
  `docker logs` warns that agents cannot commit.
- **GitHub over https:** a `GH_TOKEN` file, or `docker compose exec -it lado gh auth
  login` once (kept on the home volume).
- **ssh:** one line in `.env`; no root group. On a Mac the container makes Docker
  Desktop's root-owned socket usable by its user at each start; on Linux the socket of the
  host's user works as it is.
- **Logins of the agent CLIs:**
  - Claude Code: the `CLAUDE_CODE_OAUTH_TOKEN` file, or one login inside.
  - OpenCode and Kilo: `opencode auth login` / `kilo auth login` inside, or a model
    provider's key file.
  - Codex is a later step (T15).
- **Outside the container nothing changes** unless `LADO_ENV_DIR` is set: then a native
  LADO reads such a folder too.

Limits:
- The variables are the same for every session of one container. Sessions that need
  other values (another Yougile company, another GitHub account) run in another LADO
  container, until the profiles task.
- Every agent of a container can read every variable given to it.
- Variables cannot be set from the UI yet; that comes with profiles.

## Acceptance criteria

- **AC-1.** With `LADO_ENV_DIR` naming a folder that holds `YOUGILE_API_KEY`, an agent
  started after it has the variable with the file's value (one trailing newline dropped),
  over the login shell's; agents started before do not change.
- **AC-2.** A kit whose MCP server has `env: {KEY: ${YOUGILE_API_KEY}}` starts when only
  the folder has the variable; without the file the start is refused as today.
- **AC-3.** A file with a bad name, a reserved name (`PATH`, `HOME`, `LADO_*`, …), over
  64 KiB, not text, unreadable, or in a subfolder is not applied. It is named with its
  reason by `lado doctor` and in the warnings of a session's start and resume. Dotfiles
  are passed over silently.
- **AC-4.** A file named after a variable that LADO or the agent's provider sets keeps
  LADO's value and is named in that launch's warnings.
- **AC-5.** No value of the folder appears in LADO's logs, `lado.db`, `lado log`, the API,
  `lado doctor`, the bug report, or `docker inspect` (canary test).
- **AC-6.** In the container, `LADO_GIT_NAME` and `LADO_GIT_EMAIL` make an agent's commit
  carry that author and committer; without them `docker logs` warns once and the server
  starts.
- **AC-7.** With `GH_TOKEN` in `secrets/`, `git credential fill` for `https://github.com`
  in an agent's shell gives that token; `gh auth token` prints it.
- **AC-8.** With `LADO_SSH_AGENT` naming a socket owned by root (Docker Desktop's form), an
  agent's `ssh-add -l` lists the agent's keys after a start and after a restart, and
  `lado` is not in group 0.
- **AC-9.** With a socket owned by the projects' owner (Linux), the keys are listed and the
  socket's owner is unchanged.
- **AC-10.** Without `LADO_SSH_AGENT` agents get no `SSH_AUTH_SOCK` from the image and
  `docker logs` has no ssh line.
- **AC-11.** `sudo -n true` as `lado` still fails; the ssh rule's program with any argument
  refuses, and with any variable does only its one chown.
- **AC-12.** compose refuses without the `secrets/` folder (or `LADO_SECRETS`) and names
  it; the headers of compose.yaml and the Dockerfile give every step above.
- **AC-13.** Without `LADO_ENV_DIR`, native LADO behaves exactly as before (all existing
  tests green).

## Manual check (for the PR)

On the Mac, with Docker Desktop running:

1. `cd` into a fresh folder (e.g. `~/lado-check-76`), then `env | grep LADO` and `unset`
   every variable it prints (stale variables broke LAD-69's and LAD-73's checks).
2. Build the branch's image from a checkout of the pull request's branch: `git fetch
   origin && git switch feature/lad-76-container-secrets-git && make docker` (gives
   `lado:local`).
3. In `~/lado-check-76`: copy `docker/compose.yaml`; make `secrets` with `mkdir -m 700
   secrets`; put your real `GH_TOKEN`, `YOUGILE_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN`
   there (`printf %s "$(pbpaste)" > secrets/GH_TOKEN` per value); write `.env` with
   `LADO_IMAGE=lado:local`, `LADO_VERSION=0.40.0`, `LADO_PROJECTS=$HOME/projects`,
   `LADO_GIT_NAME`, `LADO_GIT_EMAIL`, `LADO_SSH_AGENT=/run/host-services/ssh-auth.sock`.
4. `docker compose up -d`, then `docker compose logs lado`: no git or ssh warning.
5. `docker compose exec lado lado doctor`: `Variables from outside` lists the three names;
   no `[FAIL]`.
6. `docker inspect $(docker compose ps -q lado) | grep -c -e ghp_ -e <a piece of your
   Yougile key>`: prints `0`.
7. `docker compose exec lado lado ui --no-open`, open the link, start a session with kits
   `sdlc` and `tracker-yougile` on a real repository of `~/projects`; ask the supervisor to
   read a tracker task. It answers with the task (the tracker's MCP server got the key).
8. Ask the supervisor to have a worker commit a file. On the host, `git log -1
   --format='%an <%ae>'` in the worktree shows your name and email.
9. Ask a worker to `git push` a branch to a real repository of yours, once over ssh (an
   `git@github.com:` remote) and once over https (`https://github.com/...`); both succeed.
   Delete the branches after.
10. Ask a worker to run `gh api user --jq .login`: your login.
11. `docker compose restart`, then `docker compose exec lado ssh-add -l` in a login shell
    (`docker compose exec lado bash -lc 'ssh-add -l'`): your keys.
12. Clean up: `docker compose down -v` in `~/lado-check-76` (your own project only), and
    remove the folder.
