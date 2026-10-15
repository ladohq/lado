## ADDED Requirements

### Requirement: The image takes the agents' variables from a secrets folder

The image SHALL set `LADO_ENV_DIR=/run/secrets` for the UI server and `docker exec` (the
processes that launch agents), so the agents get the variables of the files mounted there
(capability agent-variables).
- `docker/compose.yaml` SHALL bind the folder `LADO_SECRETS` names (default `./secrets`,
  next to the file) read-only at `/run/secrets`, refusing to start when that folder does
  not exist, rather than letting Docker make it.
- No variable for the agents SHALL be set through compose's `environment:` or the image's
  `ENV`, and `LADO_AGENT_ENV=inherit` SHALL not be set, so no value is in `docker
  inspect`.
- The headers SHALL say to make the folder with mode 700 and to put one file per variable
  in it (`GH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, a kit's key such as `YOUGILE_API_KEY`, a
  model provider's key). A new file reaches the agents started after it, with no
  restart. Each LADO container has its own folder, and every agent of one container can
  read every variable given to it.

#### Scenario: A kit that needs a variable starts
- **WHEN** a container runs with a folder holding `LADO_TEST_KEY` mounted at
  `/run/secrets`, and a session starts there with a kit whose MCP server has
  `env: {KEY: ${LADO_TEST_KEY}}`
- **THEN** the session starts, its supervisor's process has `LADO_TEST_KEY` with the
  file's value, and `docker inspect` of the container does not contain the value

#### Scenario: compose without the folder
- **WHEN** `docker compose up -d` runs in a folder without `secrets/` and without
  `LADO_SECRETS`
- **THEN** compose refuses and names the missing path

### Requirement: The container gives the agents the human's git identity

At every start of the container, the entrypoint, running as `lado`, SHALL write
`LADO_GIT_NAME` and `LADO_GIT_EMAIL`, when set and not empty, to `lado`'s global git
config (`user.name`, `user.email`) on the home volume. A repository's own config still
wins. When either is still missing from git's config after that, `docker logs` SHALL get
one line: `lado: warning: git has no user.name or user.email: agents cannot commit; set
LADO_GIT_NAME and LADO_GIT_EMAIL`. `docker/compose.yaml` SHALL pass both from `.env`, empty
by default.

#### Scenario: An agent's commit
- **WHEN** the container runs with `-e LADO_GIT_NAME="Ann Lee" -e
  LADO_GIT_EMAIL=ann@example.com` and an agent's shell commits in a worktree with no `-c`
- **THEN** the commit's author and committer are `Ann Lee <ann@example.com>`

#### Scenario: No identity
- **WHEN** the container runs without either variable on a fresh home volume
- **THEN** `docker logs` has the warning line, and the server starts

#### Scenario: A later change
- **WHEN** the container is made again with another `LADO_GIT_EMAIL` on the same home
  volume
- **THEN** git's global `user.email` is the new one

### Requirement: git over https to GitHub uses gh's token

The image's system git config SHALL make `gh auth git-credential` the only credential
helper for `https://github.com`. With `GH_TOKEN` in an agent's environment, or after `gh
auth login` in the container (its token in `~/.config/gh` on the home volume), git SHALL
get that token for `https://github.com` with no prompt and no extra step.

#### Scenario: The token from the secrets folder
- **WHEN** the secrets folder holds `GH_TOKEN` with a fake value and an agent's shell runs
  `git credential fill` for `protocol=https`, `host=github.com`
- **THEN** git prints `password=<that value>`

### Requirement: The host's ssh agent reaches the agents without root's group

`docker/compose.yaml` SHALL bind the path that `LADO_SSH_AGENT` names (default
`/dev/null`: no ssh agent) at `/run/lado/ssh-agent.sock`, refusing to start when that
path does not exist. When that path in the container is a socket, the image's profile
SHALL set `SSH_AUTH_SOCK=/run/lado/ssh-agent.sock` for every login shell, so for every
agent.

At every start, the entrypoint SHALL check, as `lado`, whether `lado` can use the socket:
- when it cannot and the socket belongs to uid 0, it SHALL run through `sudo` the image's
  program `/usr/local/bin/lado-ssh-agent-socket`, which takes no argument and keeps no
  variable of its caller (no `SETENV`). That program SHALL give that one path, only when
  it is a socket that is no symbolic link and belongs to uid 0, to `lado`'s uid, keeping
  its group.
- when `lado` still cannot use it, `docker logs` SHALL get one line, `lado: warning: lado
  (uid <uid>) cannot use the ssh agent socket of uid <owner>: <reason>`, and the server
  SHALL start.

The container SHALL need no `group_add`. The headers SHALL give `LADO_SSH_AGENT` for a
Mac (`/run/host-services/ssh-auth.sock`, Docker Desktop's) and for Linux (the host's
`$SSH_AUTH_SOCK`), and SHALL say that every agent of the container may then use the
host's keys.

#### Scenario: Docker Desktop's root-owned socket
- **WHEN** an ssh agent holding a test key listens on a socket owned by uid 0 at
  `/run/lado/ssh-agent.sock` (made by another container on a shared volume) and LADO's
  container starts, or restarts
- **THEN** `ssh-add -l` in an agent's login shell lists the test key, and `id -G` of
  `lado` has no 0

#### Scenario: A Linux host's socket of the projects' owner
- **WHEN** the socket belongs to the uid of the projects' owner, which `lado` takes
- **THEN** `ssh-add -l` in an agent's login shell lists the key, and the socket's owner is
  unchanged

#### Scenario: No ssh agent
- **WHEN** `LADO_SSH_AGENT` is not set
- **THEN** agents have no `SSH_AUTH_SOCK` from the image, and `docker logs` has no ssh line

#### Scenario: The rule gives no root
- **WHEN** an agent runs `sudo -n /usr/local/bin/lado-ssh-agent-socket` with any variable
  or argument
- **THEN** it can at most give that socket to `lado`, and `sudo -n true` fails

### Requirement: The headers say how the agents log in and get access

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL say:
- how to give the agents variables (the secrets folder, one file per variable);
- the git identity (`LADO_GIT_NAME`, `LADO_GIT_EMAIL`);
- GitHub over https (`GH_TOKEN` in the folder, or `gh auth login` inside);
- the ssh agent (`LADO_SSH_AGENT` for a Mac and for Linux);
- the logins of the agent CLIs: Claude Code by `CLAUDE_CODE_OAUTH_TOKEN` (from `claude
  setup-token`) in the folder or one login inside; OpenCode and Kilo by `opencode auth
  login` and `kilo auth login` inside (kept on the home volume) or a model provider's key
  in the folder. Codex's login is not covered.

#### Scenario: The steps are in the headers
- **WHEN** `tests/test_docker.py` reads the headers
- **THEN** each names `secrets`, `LADO_GIT_NAME`, `LADO_GIT_EMAIL`, `GH_TOKEN`, `gh auth
  login`, `LADO_SSH_AGENT`, `CLAUDE_CODE_OAUTH_TOKEN`, `opencode auth login` and `kilo auth
  login`

## MODIFIED Requirements

### Requirement: The image's user takes the projects folder's owner

At a container's first start, before the UI server starts, the image SHALL give its user
`lado` the uid and gid of the owner of `LADO_REPOS`'s folder, unless that owner's uid is 0
(how Docker Desktop shows a bind mount) or equal to `lado`'s already; a gid of 0, root's
group, SHALL never be taken (`lado` keeps its own group). It SHALL then give
`lado` everything under `/home/lado` whose owner is not `lado`'s uid and gid. The server,
`docker exec <container> <command>` with no `-u`, and every agent SHALL run as `lado`
with that uid. The change SHALL be made by a step that runs as root once per container
and, first of all, removes its way to it (a sudo rule for the entrypoint alone), so
that no process started after it, an agent included, can become root through it; the
image's one other sudo rule, for the ssh agent's socket (requirement "The host's ssh agent
reaches the agents without root's group"), runs one fixed program that takes no argument
and no variable and gives no root shell. Where
the image's entrypoint was replaced, the rule stays; the root step SHALL then run no
program chosen by its caller's environment (its commands by a fixed PATH or full paths,
the caller's PATH given back only after the drop to `lado`), so that the rule runs only
that step's own work. A container whose settings forbid becoming root (no-new-privileges,
capabilities dropped) or whose root file system is read-only SHALL start as before, `lado` with uid 1000 and the agents'
`LADO_REPOS` the image's `/projects`, with one warning line in `docker logs`; a step of the
root run that fails SHALL be a warning line, and the server SHALL start anyway. A
restart of the same container SHALL keep the uid it took. A folder `LADO_REPOS` that is no
folder in the container, or one `lado` may not write in, SHALL be named in `docker logs`
with one warning line, and the server SHALL start anyway.

#### Scenario: A Linux host's user

- **WHEN** the human's projects folder, owned by uid 1001 and gid 1001 on a Linux host
  (GitHub's runner), is mounted at its path with `LADO_REPOS` set to it, and an agent of
  the container writes a file and a commit there
- **THEN** `docker exec <container> id -u` prints 1001, and on the host the file and the
  commit's objects belong to uid 1001

#### Scenario: Docker Desktop shows the owner as 0

- **WHEN** `LADO_REPOS`'s folder is owned by uid 0 in the container
- **THEN** `lado` keeps uid 1000, and the server starts

#### Scenario: Recreated with another owner, the same home volume

- **WHEN** a container whose projects belong to uid 2001 has run with home volume H, and a
  new container of the image starts with H and projects that belong to uid 2002
- **THEN** in the new container `id -u` prints 2002, nothing under `/home/lado` belongs to
  another uid, the server answers `/api/health`, `lado doctor` prints no `[FAIL]`, and
  `lado ls` works

#### Scenario: Projects of root's group

- **WHEN** `LADO_REPOS`'s folder is owned by uid 2001 and gid 0
- **THEN** `id -u` in the container prints 2001 and `id -g` 1000

#### Scenario: The entrypoint replaced

- **WHEN** the container runs with `--entrypoint`, so the sudo rule stays, and `lado` runs
  the entrypoint through it with a `setpriv` of its own first on the PATH it hands over
- **THEN** that `setpriv` does not run, and the command runs as `lado`

#### Scenario: The container may not become root

- **WHEN** the container runs with `--security-opt no-new-privileges` or `--cap-drop ALL`
  and projects owned by uid 2001
- **THEN** the server answers `/api/health`, `id -u` prints 1000, and `docker logs` has a
  line `lado: warning: the container may not become root (no-new-privileges or dropped
  capabilities): lado keeps uid 1000 instead of the owner's of <path>, and the agents'
  LADO_REPOS is /projects`

#### Scenario: A read-only root file system

- **WHEN** the container runs with `--read-only --tmpfs /tmp` and projects owned by uid
  2001
- **THEN** the server answers `/api/health`, `id -u` prints 1000, and `docker logs` has a
  line `lado: warning: the container's root file system is read-only: lado keeps uid 1000
  instead of the owner's of <path>, and the agents' LADO_REPOS is /projects`

#### Scenario: A restart

- **WHEN** a container that took uid 2001 is restarted with `docker restart`
- **THEN** it runs as uid 2001 again and the server answers

#### Scenario: No way to root is left

- **WHEN** the container has started
- **THEN** `sudo -n true` run as `lado` in it fails

#### Scenario: The projects folder is not writable

- **WHEN** `LADO_REPOS`'s folder belongs to uid 0 and is not writable by others
- **THEN** `docker logs` has a line `lado: warning: LADO may not write in LADO_REPOS
  <path>`, and the server starts

#### Scenario: LADO_REPOS is not mounted

- **WHEN** the container runs with `-e LADO_REPOS=/home/me/projects` and nothing is
  mounted there
- **THEN** `docker logs` has a line `lado: warning: LADO_REPOS is not a folder in the
  container: /home/me/projects; mount the host's folder at this same path`, and the server
  starts

