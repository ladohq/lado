## Context

LADO's image (`docker/`) starts `lado server` under tini as user `lado`. Its entrypoint
(`entrypoint.sh`) has three phases:
1. at the first start of a container (the marker `/etc/lado/first-start`), `lado`
   becomes root once through a sudo rule for the entrypoint alone;
2. that root run deletes the rule and the marker first, gives `lado` the projects
   owner's uid, and writes `LADO_REPOS` to `/etc/profile.d/lado-repos.sh`;
3. every start then warns about `LADO_REPOS` and execs the server.

An agent's environment is resolved anew for each launch by `agent_env.resolve()`, in
`runtime._base_env()`:
- `$SHELL -ilc` run from a few variables (`HOME USER LOGNAME SHELL TMPDIR LANG
  SSH_AUTH_SOCK`), so the image's `/etc/profile.d/*.sh` and the home volume's dotfiles;
- or, with `LADO_AGENT_ENV=inherit`, the starting process's environment.

`runtime._launch_env` then lays LADO's variables (`providers.agent_env`: `LADO_HOME`,
`LADO_SESSION`, `LADO_AGENT`, …) and the provider's (`launch.env`) on top. The kit check of
an MCP server's `${NAME}` (`kits.ResolvedAgent.mcp_servers`) and `_check_commands` read
that base environment.

Facts checked for this design on Docker Desktop 29.7 (macOS, arm64) with `lado:local`:
- `/run/host-services/ssh-auth.sock` is `srw-rw---- 0 0` in a container, and `ssh-add -l`
  as `lado` fails with `Permission denied`.
- After `chown 1000` as root the key is listed, and the owner survives `docker restart`.
  It is one socket of Docker Desktop's VM, shared by its containers, and comes back as
  root's after the VM restarts.
- With `GH_TOKEN=x` and `credential.https://github.com.helper` set to `!/usr/bin/gh auth
  git-credential`, `git credential fill` prints `username=x-access-token`, `password=x`
  with no network.
- `gh auth token` prints `GH_TOKEN`.
- A bind of `/dev/null` at `/run/lado/ssh-agent.sock` works on Docker Desktop and is a
  character device there, not a socket.
- The image has no editor (no `vi`, `nano`).

Root cause: the agents' one source of environment, the login shell, cannot be fed from
outside the container without putting values in its configuration. git has neither an
identity nor a credential helper, and the ssh socket belongs to root.

## Options

**How variables enter the container:**
1. **A folder of files (Docker's `/run/secrets` form) that LADO reads for each launch**
   (chosen).
   - Values never sit in the container's configuration, and files are edited on the
     host with any editor.
   - It is the same folder a future Docker manager or compose `secrets:` fills, and the
     read-only base of the later profile `default`.
   - Long-term cost: one small layer in `agent_env`, with rules and `lado doctor`.
2. **The image's profile script sources the folder** (`/etc/profile.d`). No Python, but
   it parses files in `sh` with no warnings, does not exist outside the image, and the
   profiles task would redo it in LADO.
3. **A command in the container that writes a 600 file on the volume** (`lado-secret
   set`). The human types every value through `docker exec`. A launcher or manager cannot
   give values at the container's start, and the file dies with the volume.
4. **compose `environment:` / `LADO_AGENT_ENV=inherit`.** Refused: the values are in
   `docker inspect`, and `inherit` gives the agents everything of the container.

**ssh without root's group:**
1. **A second, narrow sudo rule run at every start** (chosen). It runs one fixed program
   that only gives a root-owned socket at a fixed path to `lado`. An agent that runs it
   gains nothing it does not have through `SSH_AUTH_SOCK` already.
2. **chown in the first-start root phase only.** It breaks after every Docker Desktop
   restart, which makes the socket root's again while the container only restarts.
3. **A root relay (socat) started by the root phase.** It is a root process for the
   container's life, and it is gone after a restart too.
4. **`group_add: ["0"]`.** It works, and it is the extra right this task removes.

## Decisions

- **D1. `agent_env.resolve()` takes the outside folder.**
  - The base environment for an agent becomes `resolve()`'s source (shell or inherit),
    then the folder's valid files. The point stays one, `runtime._base_env()`, so every
    launch, the kit checks and `_check_commands` see the same environment.
  - The folder is read at each call; nothing is cached, since a new file must reach the
    next agent.
  - A small `Outside` result (values and the files not used, with reasons) is returned
    by a function of its own, `agent_env.outside()`. `resolve()` stays the one entry
    that merges it; `lado doctor` and the start's warnings read `outside()`.
  - Why: one source of truth, one merge point.
- **D2. The rules of a file**:
  - only regular files directly in the folder;
  - `.`-names are passed over silently (Docker and editors leave such files);
  - a valid variable name (`[A-Za-z_][A-Za-z0-9_]*`; lower case is allowed, as compose
    names secrets so);
  - not reserved: `HOME USER LOGNAME SHELL PATH PWD OLDPWD SHLVL _ TERM TERM_PROGRAM
    TERM_PROGRAM_VERSION TMUX TMUX_PANE`, `LADO_*`;
  - at most 64 KiB;
  - UTF-8 with no NUL;
  - one trailing `\n` or `\r\n` dropped, nothing else trimmed.

  Why: `PATH` and the identity of the shell must stay the login shell's, or `lado
  doctor`'s agent PATH and the agent's would differ. `LADO_*` is LADO's own namespace.
  The size and text limits keep a stray binary from reaching an environment.
- **D3. A name LADO or the provider sets for the launch keeps their value** (the existing
  order of `_launch_env`). The launch's warnings name the file once per launch. Why: no
  silent drops, and a provider's config variable must never be replaced from outside.
- **D4. Files not used are warned about at a session's start and resume**
  (`Started.warnings`, `lado start`'s stderr) and by `lado doctor`, not at each
  `spawn_worker`: the folder is the container's, and a warning per worker would repeat
  the same line. A provider-set name (D3) is warned about at every launch it happens in,
  `spawn_worker` included, since it depends on the agent's provider.
- **D5. `LADO_ENV_DIR` is an absolute path; anything else is `lado doctor`'s warning** and
  is not read. Unset or empty: no layer. The image sets it in `ENV` (the server and
  `docker exec` launch agents). It is a LADO variable, so it is not passed into agents
  through the folder.
- **D6. compose binds `${LADO_SECRETS:-./secrets}` at `/run/secrets` read-only** with the
  long syntax and `create_host_path: false`. Docker on Linux would otherwise make the
  missing folder as root, and the human could then not add files without sudo. The
  header's first steps make it: `mkdir -m 700 secrets`. `docker run`'s header line adds
  `-v "$PWD/secrets:/run/secrets:ro"`.
- **D7. git identity in phase 3 of the entrypoint, at every start, as `lado`**:
  `git config --global user.name "$LADO_GIT_NAME"` when it is set and not empty, the same
  for the email; then a warning when `git config user.name` or `user.email` is still
  empty.
  - Why every start: a changed `.env` with `up -d` makes a new container on the same
    volume, and it must take the new value; no root is needed.
  - The global config, not the system one, so a repository's own config wins.
  - Values with spaces or quotes go as one argument; the entrypoint never evals them.
- **D8. `gh` as git's credential helper for github.com, in the image's system config**:
  `credential.https://github.com.helper` first set to empty (it resets inherited
  helpers), then `!/usr/bin/gh auth git-credential`, the two lines `gh auth setup-git`
  writes.
  - It works with `GH_TOKEN` from the folder, and with `gh auth login` inside, whose
    `hosts.yml` lies on the home volume.
  - Other hosts are out of scope.
- **D9. ssh: compose binds `${LADO_SSH_AGENT:-/dev/null}` at `/run/lado/ssh-agent.sock`**
  with `create_host_path: false`. `/dev/null` means none and keeps the line valid on every
  host.
  - The image makes `/run/lado` root's, mode 755, so no agent can plant a file there.
  - `profile.sh` exports `SSH_AUTH_SOCK` only when `[ -S /run/lado/ssh-agent.sock ]`.
    tests/test_docker.py's ENV/profile parity check learns that this line is the
    profile's alone, because the server needs no ssh agent.
- **D10. `/usr/local/bin/lado-ssh-agent-socket`** (`docker/ssh-agent-socket.sh`, root's,
  755) and the rule `lado ALL=(root) NOPASSWD: /usr/local/bin/lado-ssh-agent-socket`
  in `/etc/sudoers.d/lado-ssh-agent` (0440, `visudo -c`).
  - The rule has no `SETENV`, so sudo's `env_reset` gives the program a clean
    environment.
  - With an argument, the program refuses.
  - It sets `PATH=/usr/bin:/bin` and checks with `test` and `stat` that the fixed path is
    a socket (`-S`), not a symlink (`-L`), and owned by uid 0.
    Then it runs `chown --no-dereference "$(id -u lado)" /run/lado/ssh-agent.sock`,
    group unchanged.
  - The entrypoint's phase 3 calls it only when the socket exists, `lado` cannot use it
    (`ssh-add -l` exit 2: no agent connection) and its owner is 0, and only when
    `may_become_root` holds (else the warning).
  - On Docker Desktop the chown changes the VM's one socket for every container. Its
    group stays 0, so other containers relying on root's group keep their access, and
    LADO containers there are uid 1000 alike.
  - Why: the narrowest root step that holds over restarts of Docker Desktop.
- **D11. The first-start rule is unchanged.** The new rule lives in its own file, so the
  root phase still deletes only `/etc/sudoers.d/lado-entrypoint`. The container spec's
  wording changes, and its scenario "No way to root is left" (`sudo -n true` fails) holds
  as it is.
- **D12. Values never leave the launch file.** `agent_env` raises no exception carrying a
  value. An error names the file and its reason only. The existing `env.json` (mode 600,
  removed once read) stays the one place a value is written. A unit test with a canary
  value and a container check of `docker inspect` hold it.
- **D13. Version: minor**, a new image feature and a new LADO variable. CHANGELOG lines go
  under `## 0.40.0 (unreleased)`. No schema, API, MCP or UI change, so no `make
  web-types`.
- **D14. Test layers**:
  - unit (`tests/test_agent_env.py`: the rules, precedence, warnings, canary;
    `tests/test_runtime.py`: start and spawn warnings, the kit check seeing a variable;
    `tests/test_doctor.py`; `tests/test_docker.py`: compose, Dockerfile, profile, headers,
    rule file);
  - integration (`tests/integration/`: a fake-agent session with `LADO_ENV_DIR` whose
    worker's environment has the variable, and a folder kit whose MCP server needs it
    starts; this crosses processes, the window's `lado.agent_env`);
  - container (`tests/container/test_access.py`, new: the git identity, the credential
    helper, the kit with a variable and `docker inspect`, the ssh agent through a
    root-owned socket on a shared volume and through one of the projects' owner).

  A live test is not needed: no provider changes.

## Risks / Trade-offs

- **Every agent of a container can read every variable given to it** (one OS user).
  → The headers say so; another container is the isolation. Profiles will not change
  that either.
- **A Docker Desktop VM restart makes the socket root's again.** → The entrypoint runs at
  every container start, and Docker Desktop's restart restarts the containers too.
- **A Linux host's `SSH_AUTH_SOCK` path changes per login.** → The header says to point
  `LADO_SSH_AGENT` at a stable socket, or to recreate the container after a new login.
  This is documented, not solved.
- **A file left in `secrets/` by mistake becomes a variable.** → Only valid names count,
  dotfiles are passed over, and `lado doctor` lists the names.
